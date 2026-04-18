"""
REST API endpoints for the dashboard and request management.
The frontend calls these to display request history, details, and stats.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.models.db_models import AccountStatus, InfraRequestRecord, RequestEvent, RequestStatus, TeamAccount
from app.models.requests import REQUEST_TYPE_MAP
from app.models.schemas import EventOut, RequestDetail, RequestOut, StatsOut, StatusUpdate
from app.config import settings
from app.services.renderer import renderer, BLUEPRINTS
from app.services.github_pr import github_service
from app.routers.ws import broadcast_request_created, broadcast_status_changed
from app.routers.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["requests"])
logger = structlog.get_logger()


# ─── Create request (the real entrypoint) ────────────────────────────────────

class CreateRequestPayload(BaseModel):
    """Payload from the frontend form. request_type + all type-specific fields."""
    request_type: str
    # All other fields are passed through and validated against the type-specific model


@router.post("/requests", response_model=RequestDetail, status_code=201)
async def create_request(
    payload: dict,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequestDetail:
    """
    Create a new infrastructure request from the portal UI.
    Validates against the Pydantic model, saves to DB, and returns the record.
    """
    request_type = payload.get("request_type", "")
    if request_type not in REQUEST_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown request type: '{request_type}'. "
                   f"Valid types: {list(REQUEST_TYPE_MAP.keys())}",
        )

    # Generate ticket key (INFRA-XXXX)
    ticket_key = await _generate_ticket_key(db)

    # Auto-fill jira_ticket_key since the UI won't have one
    payload["jira_ticket_key"] = ticket_key

    # Validate against the type-specific Pydantic model
    model_class = REQUEST_TYPE_MAP[request_type]
    try:
        validated = model_class(**payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Auto-fill requester from JWT if not provided
    if not payload.get("requester_email"):
        payload["requester_email"] = user.email

    # Extract resource name
    resource_name = renderer._get_resource_name(validated)
    branch_name = f"infra/{ticket_key}-{request_type}"

    # Resolve target repo: prefer team's own repo from account, fall back to central
    target_github_group = payload.get("github_group") or settings.iac_github_org
    target_github_repo = payload.get("github_repo") or settings.infra_live_repo
    if not payload.get("github_group") and validated.team_name:
        acct_result = await db.execute(
            select(TeamAccount)
            .where(TeamAccount.team_name == validated.team_name)
            .where(TeamAccount.status == AccountStatus.ACTIVE)
        )
        acct = acct_result.scalar_one_or_none()
        if acct and acct.github_group:
            target_github_group = acct.github_group
            target_github_repo = acct.github_repo or "infra"

    # 1. Render Jinja2 templates → terragrunt.hcl files
    rendered_files: dict[str, str] = {}
    pr_url = ""
    pr_number = None
    render_error = None

    try:
        rendered_files = renderer.render(validated)
    except Exception as e:
        render_error = str(e)
        logger.warning("render_skipped", error=render_error, ticket=ticket_key)

    # 2. Ensure target repo exists (auto-create + bootstrap if not)
    if rendered_files:
        try:
            was_created = github_service.ensure_repo_exists(
                github_group=target_github_group,
                github_repo=target_github_repo,
            )
            if was_created:
                logger.info("repo_auto_created", repo=f"{target_github_group}/{target_github_repo}", ticket=ticket_key)
        except Exception as e:
            logger.warning("repo_ensure_failed", error=str(e), ticket=ticket_key)

    # 3. Create PR in team's repo
    if rendered_files:
        pr_body = (
            f"## Self-Service Infrastructure Request\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| **Ticket** | {ticket_key} |\n"
            f"| **Type** | `{request_type}` |\n"
            f"| **Environment** | `{validated.environment}` |\n"
            f"| **Team** | `{validated.team_name}` |\n"
            f"| **Resource** | `{resource_name}` |\n"
            f"| **Requester** | {validated.requester_email} |\n"
            f"| **Account** | `{validated.account_id}` |\n\n"
            f"### Files\n\n"
        )
        for fp in sorted(rendered_files.keys()):
            pr_body += f"- `{fp}`\n"
        pr_body += "\n---\n*Auto-generated by Keystone Self-Service Platform.*"

        try:
            pr_url = github_service.create_pull_request(
                github_group=target_github_group,
                github_repo=target_github_repo,
                branch_name=branch_name,
                title=f"[{ticket_key}] {request_type}: {resource_name} ({validated.environment})",
                body=pr_body,
                files=rendered_files,
                labels=["self-service", request_type, validated.environment or "default"],
            )
            if pr_url and "/pull/" in pr_url:
                try:
                    pr_number = int(pr_url.rsplit("/pull/", 1)[1].rstrip("/"))
                except (ValueError, IndexError):
                    pass
            logger.info("pr_created", pr_url=pr_url, ticket=ticket_key)
        except Exception as e:
            render_error = f"PR creation failed: {e}"
            logger.error("pr_failed", error=str(e), ticket=ticket_key)

    # 3. Save to DB
    file_paths = sorted(rendered_files.keys()) if rendered_files else []
    record = InfraRequestRecord(
        jira_ticket_key=ticket_key,
        request_type=request_type,
        status=RequestStatus.PENDING,
        requester_email=validated.requester_email,
        team_name=validated.team_name,
        cost_center=validated.cost_center,
        resource_name=resource_name,
        environment=validated.environment,
        account_id=validated.account_id,
        request_data=validated.model_dump(),
        github_group=target_github_group,
        github_repo=target_github_repo,
        pr_url=pr_url,
        pr_number=pr_number,
        branch_name=branch_name,
        files_created=len(file_paths),
        file_paths=file_paths,
        error_message=render_error,
    )
    db.add(record)

    event = RequestEvent(
        request_id=0,
        event_type="pr_created" if pr_url else "created",
        description=(
            f"PR created in {target_github_group}/{target_github_repo}: {pr_url}"
            if pr_url
            else f"{request_type} request created — {render_error or 'pending template rendering'}"
        ),
        metadata_json={"request_type": request_type, "resource_name": resource_name, "pr_url": pr_url},
    )

    await db.flush()
    event.request_id = record.id
    db.add(event)
    await db.commit()
    await db.refresh(record, attribute_names=["events"])

    logger.info("request_created", ticket=ticket_key, type=request_type, resource=resource_name, pr_url=pr_url)

    await broadcast_request_created(
        ticket_key=ticket_key,
        request_type=request_type,
        resource_name=resource_name,
        team_name=validated.team_name,
        environment=validated.environment or "",
        requester_email=validated.requester_email,
    )

    return record


async def _generate_ticket_key(db: AsyncSession) -> str:
    """Generate the next INFRA-XXXX ticket key."""
    result = await db.execute(
        select(func.count()).select_from(InfraRequestRecord)
    )
    count = result.scalar() or 0
    # Start from 3001 to avoid collision with seeded data (INFRA-2XXX)
    return f"INFRA-{3001 + count}"


# ─── List requests ───────────────────────────────────────────────────────────

@router.get("/requests", response_model=list[RequestOut])
async def list_requests(
    status: str | None = Query(None, description="Filter by status"),
    request_type: str | None = Query(None, description="Filter by request type"),
    team: str | None = Query(None, description="Filter by team name"),
    environment: str | None = Query(None, description="Filter by environment"),
    search: str | None = Query(None, description="Search jira key or resource name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RequestOut]:
    """List requests. Non-admins only see their team's requests."""
    stmt = select(InfraRequestRecord).order_by(InfraRequestRecord.created_at.desc())

    # RBAC: non-admins only see their own team
    if not user.is_admin and user.team_name:
        stmt = stmt.where(InfraRequestRecord.team_name == user.team_name)

    if status:
        stmt = stmt.where(InfraRequestRecord.status == status)
    if request_type:
        stmt = stmt.where(InfraRequestRecord.request_type == request_type)
    if team:
        stmt = stmt.where(InfraRequestRecord.team_name.ilike(f"%{team}%"))
    if environment:
        stmt = stmt.where(InfraRequestRecord.environment == environment)
    if search:
        stmt = stmt.where(
            InfraRequestRecord.jira_ticket_key.ilike(f"%{search}%")
            | InfraRequestRecord.resource_name.ilike(f"%{search}%")
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ─── Get single request ─────────────────────────────────────────────────────

@router.get("/requests/{jira_key}", response_model=RequestDetail)
async def get_request(jira_key: str, db: AsyncSession = Depends(get_db)) -> RequestDetail:
    """Get full details for a single request including timeline events."""
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.jira_ticket_key == jira_key)
        .options(selectinload(InfraRequestRecord.events))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request {jira_key} not found")
    return record


# ─── Retry failed PR creation ───────────────────────────────────────────────

@router.post("/requests/{jira_key}/retry", response_model=RequestDetail)
async def retry_request(
    jira_key: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequestDetail:
    """Retry PR creation for a request that failed. Re-renders templates and creates PR."""
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.jira_ticket_key == jira_key)
        .options(selectinload(InfraRequestRecord.events))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request {jira_key} not found")

    if record.pr_url:
        raise HTTPException(status_code=400, detail=f"PR already exists: {record.pr_url}")

    # Re-render templates from saved request_data
    request_type = record.request_type
    if request_type not in REQUEST_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown request type: {request_type}")

    model_class = REQUEST_TYPE_MAP[request_type]
    validated = model_class(**record.request_data)
    resource_name = renderer._get_resource_name(validated)
    branch_name = record.branch_name or f"infra/{jira_key}-{request_type}"

    target_github_group = record.github_group or settings.iac_github_org
    target_github_repo = record.github_repo or settings.infra_live_repo

    # Render templates
    rendered_files: dict[str, str] = {}
    try:
        rendered_files = renderer.render(validated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template rendering failed: {e}")

    if not rendered_files:
        raise HTTPException(status_code=500, detail="No files rendered")

    # Ensure repo exists
    try:
        github_service.ensure_repo_exists(
            github_group=target_github_group,
            github_repo=target_github_repo,
        )
    except Exception as e:
        logger.warning("repo_ensure_failed_retry", error=str(e), ticket=jira_key)

    # Create PR
    pr_body = (
        f"## Self-Service Infrastructure Request (Retry)\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| **Ticket** | {jira_key} |\n"
        f"| **Type** | `{request_type}` |\n"
        f"| **Environment** | `{validated.environment}` |\n"
        f"| **Team** | `{validated.team_name}` |\n"
        f"| **Resource** | `{resource_name}` |\n"
        f"| **Requester** | {validated.requester_email} |\n"
        f"| **Account** | `{validated.account_id}` |\n\n"
        f"### Files\n\n"
    )
    for fp in sorted(rendered_files.keys()):
        pr_body += f"- `{fp}`\n"
    pr_body += "\n---\n*Auto-generated by Keystone Self-Service Platform (retry).*"

    try:
        pr_url = github_service.create_pull_request(
            github_group=target_github_group,
            github_repo=target_github_repo,
            branch_name=branch_name,
            title=f"[{jira_key}] {request_type}: {resource_name} ({validated.environment})",
            body=pr_body,
            files=rendered_files,
            labels=["self-service", request_type, validated.environment or "default"],
        )
    except Exception as e:
        # Record the retry failure too
        event = RequestEvent(
            request_id=record.id,
            event_type="retry_failed",
            description=f"Retry failed: {e}",
            metadata_json={"error": str(e)},
        )
        db.add(event)
        record.error_message = f"Retry failed: {e}"
        await db.commit()
        await db.refresh(record, attribute_names=["events"])
        raise HTTPException(status_code=502, detail=f"PR creation failed on retry: {e}")

    # Update the record
    pr_number = None
    if pr_url and "/pull/" in pr_url:
        try:
            pr_number = int(pr_url.rsplit("/pull/", 1)[1].rstrip("/"))
        except (ValueError, IndexError):
            pass

    record.pr_url = pr_url
    record.pr_number = pr_number
    record.error_message = None
    record.files_created = len(rendered_files)
    record.file_paths = sorted(rendered_files.keys())

    event = RequestEvent(
        request_id=record.id,
        event_type="pr_created",
        description=f"PR created (retry) in {target_github_group}/{target_github_repo}: {pr_url}",
        metadata_json={"pr_url": pr_url, "retry": True},
    )
    db.add(event)
    await db.commit()
    await db.refresh(record, attribute_names=["events"])

    logger.info("retry_success", ticket=jira_key, pr_url=pr_url)
    return record


# ─── Dashboard stats ────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
async def get_stats(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    """Aggregated statistics. Non-admins see only their team's stats."""

    # RBAC base filter
    team_filter = []
    if not user.is_admin and user.team_name:
        team_filter = [InfraRequestRecord.team_name == user.team_name]

    # Total counts by status
    status_counts = await db.execute(
        select(InfraRequestRecord.status, func.count())
        .where(*team_filter)
        .group_by(InfraRequestRecord.status)
    )
    status_map = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in status_counts}

    total = sum(status_map.values())
    deployed = status_map.get("deployed", 0)
    pending = sum(
        status_map.get(s, 0)
        for s in ["pending", "plan_running", "awaiting_approval", "provisioning"]
    )
    failed = sum(status_map.get(s, 0) for s in ["failed", "plan_failed"])

    # By type
    type_counts = await db.execute(
        select(InfraRequestRecord.request_type, func.count())
        .where(*team_filter)
        .group_by(InfraRequestRecord.request_type)
    )
    by_type = {row[0]: row[1] for row in type_counts}

    # By team
    team_counts = await db.execute(
        select(InfraRequestRecord.team_name, func.count())
        .where(InfraRequestRecord.team_name != "", *team_filter)
        .group_by(InfraRequestRecord.team_name)
    )
    by_team = {row[0]: row[1] for row in team_counts}

    # By environment
    env_counts = await db.execute(
        select(InfraRequestRecord.environment, func.count())
        .where(InfraRequestRecord.environment != "", *team_filter)
        .group_by(InfraRequestRecord.environment)
    )
    by_environment = {row[0]: row[1] for row in env_counts}

    # Recent 10
    recent_stmt = select(InfraRequestRecord).where(*team_filter).order_by(InfraRequestRecord.created_at.desc()).limit(10)
    recent_result = await db.execute(recent_stmt)
    recent = recent_result.scalars().all()

    return StatsOut(
        total_requests=total,
        deployed=deployed,
        pending=pending,
        failed=failed,
        by_type=by_type,
        by_team=by_team,
        by_environment=by_environment,
        recent_activity=recent,
    )


# ─── CI/CD callback — update request status ─────────────────────────────────

@router.post("/requests/{jira_key}/status", response_model=RequestOut)
async def update_request_status(
    jira_key: str,
    update: StatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> RequestOut:
    """
    Called by the CI/CD pipeline (GitHub Actions) after plan/apply/destroy.
    Updates the request status and stores deployment outputs (ARNs, endpoints, etc.).
    """
    stmt = select(InfraRequestRecord).where(
        InfraRequestRecord.jira_ticket_key == jira_key
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request {jira_key} not found")

    # Validate status transition
    try:
        new_status = RequestStatus(update.status)
    except ValueError:
        valid = [s.value for s in RequestStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Valid: {valid}",
        )

    old_status = record.status
    record.status = new_status

    if update.deployment_outputs:
        record.deployment_outputs = update.deployment_outputs

    if update.error_message:
        record.error_message = update.error_message

    if new_status == RequestStatus.DEPLOYED:
        from datetime import datetime, timezone
        record.deployed_at = datetime.now(timezone.utc)

    # Create timeline event
    event = RequestEvent(
        request_id=record.id,
        event_type="status_change",
        description=f"Status changed from {old_status.value} to {new_status.value}",
        metadata_json={"old_status": old_status.value, "new_status": new_status.value, **({
            "outputs": update.deployment_outputs} if update.deployment_outputs else {}
        )},
    )
    db.add(event)

    await db.commit()
    await db.refresh(record)

    # Broadcast live status change to all connected clients
    await broadcast_status_changed(
        ticket_key=jira_key,
        request_type=record.request_type,
        resource_name=record.resource_name,
        old_status=old_status.value,
        new_status=new_status.value,
        requester_email=record.requester_email,
    )

    return record


# ─── Request timeline ────────────────────────────────────────────────────────

@router.get("/requests/{jira_key}/events", response_model=list[EventOut])
async def get_request_events(
    jira_key: str, db: AsyncSession = Depends(get_db)
) -> list[EventOut]:
    """Get the timeline of events for a request."""
    stmt = select(InfraRequestRecord).where(
        InfraRequestRecord.jira_ticket_key == jira_key
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request {jira_key} not found")

    events_stmt = (
        select(RequestEvent)
        .where(RequestEvent.request_id == record.id)
        .order_by(RequestEvent.created_at.desc())
    )
    events_result = await db.execute(events_stmt)
    return events_result.scalars().all()
