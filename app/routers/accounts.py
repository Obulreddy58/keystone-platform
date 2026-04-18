"""
Accounts Router — team account registry and account vending lifecycle.

Endpoints:
  GET  /api/accounts           — list all team accounts (with filters)
  GET  /api/accounts/stats     — aggregated account stats for dashboard
  GET  /api/accounts/{team}    — get a team's account details
  POST /api/accounts           — PO requests a new account
  POST /api/accounts/{team}/approve  — admin approves/rejects
  POST /api/accounts/{team}/status   — CI/CD callback after provisioning
  GET  /api/accounts/lookup/{team}   — lightweight lookup (returns account_id + github info)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import AccountStatus, TeamAccount
from app.models.schemas import (
    AccountApproval,
    AccountStatsOut,
    StatusUpdate,
    TeamAccountDetail,
    TeamAccountOut,
)
from app.routers.deps import CurrentUser, get_current_user, get_optional_user

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


# ─── List all team accounts ─────────────────────────────────────────────────

@router.get("", response_model=list[TeamAccountOut])
async def list_accounts(
    status: str | None = Query(None, description="Filter by status"),
    business_unit: str | None = Query(None),
    search: str | None = Query(None, description="Search team name or owner email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamAccountOut]:
    stmt = select(TeamAccount).order_by(TeamAccount.created_at.desc())

    # RBAC: non-admins only see their own team's accounts
    if not user.is_admin and user.team_name:
        stmt = stmt.where(TeamAccount.team_name == user.team_name)

    if status:
        stmt = stmt.where(TeamAccount.status == status)
    if business_unit:
        stmt = stmt.where(TeamAccount.business_unit.ilike(f"%{business_unit}%"))
    if search:
        stmt = stmt.where(
            TeamAccount.team_name.ilike(f"%{search}%")
            | TeamAccount.product_owner_email.ilike(f"%{search}%")
            | TeamAccount.team_display_name.ilike(f"%{search}%")
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ─── Account stats ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=AccountStatsOut)
async def get_account_stats(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountStatsOut:
    # RBAC base filter
    team_filter = []
    if not user.is_admin and user.team_name:
        team_filter = [TeamAccount.team_name == user.team_name]

    status_counts = await db.execute(
        select(TeamAccount.status, func.count())
        .where(*team_filter)
        .group_by(TeamAccount.status)
    )
    status_map = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1]
        for row in status_counts
    }

    bu_counts = await db.execute(
        select(TeamAccount.business_unit, func.count())
        .where(TeamAccount.business_unit != "", *team_filter)
        .group_by(TeamAccount.business_unit)
    )
    env_counts = await db.execute(
        select(TeamAccount.environment, func.count())
        .where(TeamAccount.environment != "", *team_filter)
        .group_by(TeamAccount.environment)
    )

    return AccountStatsOut(
        total_accounts=sum(status_map.values()),
        active=status_map.get("active", 0),
        pending_approval=status_map.get("pending_approval", 0),
        provisioning=status_map.get("provisioning", 0),
        by_business_unit={row[0]: row[1] for row in bu_counts},
        by_environment={row[0]: row[1] for row in env_counts},
    )


# ─── Get single team account ────────────────────────────────────────────────

@router.get("/{team_name}", response_model=TeamAccountDetail)
async def get_account(
    team_name: str, db: AsyncSession = Depends(get_db)
) -> TeamAccountDetail:
    stmt = select(TeamAccount).where(TeamAccount.team_name == team_name)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")
    return record


# ─── Lightweight team lookup (for resource request forms) ────────────────────

@router.get("/lookup/{team_name}")
async def lookup_team(
    team_name: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Quick lookup used by other request forms.
    When a team member picks their team from a dropdown, the UI calls this
    to auto-fill account_id, github_group, and github_repo.
    """
    stmt = select(TeamAccount).where(TeamAccount.team_name == team_name)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not registered")
    if record.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Team '{team_name}' account is not active (status: {record.status.value})",
        )
    return {
        "team_name": record.team_name,
        "account_id": record.account_id,
        "github_group": record.github_group,
        "github_repo": record.github_repo,
        "environment": record.environment,
        "oidc_role_arn": record.oidc_role_arn,
    }


# ─── Register a new account request ─────────────────────────────────────────

@router.post("", response_model=TeamAccountOut, status_code=201)
async def request_account(
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> TeamAccountOut:
    """
    Product owner submits a request for a new AWS account.
    The account starts in 'pending_approval' until an admin approves it.
    """
    # Check for duplicate team name
    existing = await db.execute(
        select(TeamAccount).where(TeamAccount.team_name == payload.get("team_name", ""))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Team '{payload['team_name']}' already has an account registered",
        )

    record = TeamAccount(
        team_name=payload["team_name"],
        team_display_name=payload.get("team_display_name", payload["team_name"]),
        product_owner_email=payload["product_owner_email"],
        cost_center=payload.get("cost_center", ""),
        business_unit=payload.get("business_unit", ""),
        account_name=f"{payload['team_name']}-{payload.get('environment', 'dev')}",
        account_email=payload.get("account_email", ""),
        environment=payload.get("environment", "dev"),
        github_group=payload.get("github_group", ""),
        github_repo=payload.get("github_repo", "infra"),
        jira_ticket_key=payload.get("jira_ticket_key", ""),
        status=AccountStatus.PENDING_APPROVAL,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ─── Admin approves or rejects ───────────────────────────────────────────────

@router.post("/{team_name}/approve", response_model=TeamAccountOut)
async def approve_account(
    team_name: str,
    approval: AccountApproval,
    db: AsyncSession = Depends(get_db),
) -> TeamAccountOut:
    """
    Admin approves or rejects a pending account request.

    On approval:
    - Status moves to 'approved'
    - The platform then creates a PR with account-factory + account-baseline config
    - After merge + terraform apply, the CI/CD callback sets status to 'active'
    """
    stmt = select(TeamAccount).where(TeamAccount.team_name == team_name)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    if record.status != AccountStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: current status is '{record.status.value}', expected 'pending_approval'",
        )

    if not approval.approved:
        record.status = AccountStatus.CLOSED
        record.error_message = f"Rejected by {approval.approved_by}: {approval.reason}"
        await db.commit()
        await db.refresh(record)
        return record

    record.is_admin_approved = True
    record.approved_by = approval.approved_by
    record.approved_at = datetime.now(timezone.utc)
    record.status = AccountStatus.APPROVED
    await db.commit()
    await db.refresh(record)
    return record


# ─── CI/CD callback — after account provisioning ───────────────────────────

@router.post("/{team_name}/status", response_model=TeamAccountOut)
async def update_account_status(
    team_name: str,
    update: StatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> TeamAccountOut:
    """
    Called by CI/CD after the account-factory + account-baseline terraform apply.

    Expected statuses:
    - provisioning: terraform apply started
    - active: everything deployed, account is ready
    - failed: something went wrong (error_message included)
    """
    stmt = select(TeamAccount).where(TeamAccount.team_name == team_name)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    try:
        new_status = AccountStatus(update.status)
    except ValueError:
        valid = [s.value for s in AccountStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Valid: {valid}",
        )

    record.status = new_status

    if update.deployment_outputs:
        record.provisioning_outputs = update.deployment_outputs
        # Extract key outputs from the terraform apply
        record.account_id = update.deployment_outputs.get("account_id", record.account_id)
        record.oidc_role_arn = update.deployment_outputs.get(
            "github_actions_role_arn", record.oidc_role_arn
        )
        record.state_bucket = update.deployment_outputs.get(
            "terraform_state_bucket", record.state_bucket
        )

    if update.error_message:
        record.error_message = update.error_message

    if new_status == AccountStatus.ACTIVE:
        record.provisioned_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(record)
    return record
