"""
Admin Router — user management, platform activity, system health.

All endpoints require admin role (validated via JWT).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import (
    InfraRequestRecord,
    RequestEvent,
    RequestStatus,
    TeamAccount,
    User,
    UserRole,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Auth helper ─────────────────────────────────────────────────────────────

async def _require_admin(request: Request, db: AsyncSession, token: str = "") -> User:
    """Validate JWT and ensure user is admin. Supports Bearer header or query param."""
    # Prefer Authorization header, fall back to query param
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    request_count: int = 0
    model_config = {"from_attributes": True}


class UpdateUserRole(BaseModel):
    role: str  # "admin" or "viewer"


class UpdateUserStatus(BaseModel):
    is_active: bool


# ─── User management ────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List all platform users with their request counts."""
    await _require_admin(request, db)

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    # Get request counts per user email
    req_counts = await db.execute(
        select(InfraRequestRecord.requester_email, func.count())
        .group_by(InfraRequestRecord.requester_email)
    )
    count_map = {row[0]: row[1] for row in req_counts}

    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "request_count": count_map.get(u.email, 0),
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    body: UpdateUserRole,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role (admin/viewer)."""
    admin = await _require_admin(request, db)

    if body.role not in ("admin", "viewer"):
        raise HTTPException(400, "Role must be 'admin' or 'viewer'")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot change your own role")

    user.role = UserRole.ADMIN if body.role == "admin" else UserRole.VIEWER
    await db.commit()
    return {"status": "updated", "user_id": user_id, "new_role": body.role}


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    body: UpdateUserStatus,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a user account."""
    admin = await _require_admin(request, db)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot disable your own account")

    user.is_active = body.is_active
    await db.commit()
    return {"status": "updated", "user_id": user_id, "is_active": body.is_active}


# ─── Platform activity / audit log ──────────────────────────────────────────

@router.get("/activity")
async def platform_activity(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Recent platform-wide activity (timeline events across all requests)."""
    await _require_admin(request, db)

    stmt = (
        select(RequestEvent, InfraRequestRecord.jira_ticket_key, InfraRequestRecord.request_type, InfraRequestRecord.requester_email)
        .join(InfraRequestRecord, RequestEvent.request_id == InfraRequestRecord.id)
        .order_by(RequestEvent.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "description": ev.description,
            "ticket_key": ticket_key,
            "request_type": req_type,
            "requester_email": requester,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "metadata": ev.metadata_json,
        }
        for ev, ticket_key, req_type, requester in rows
    ]


# ─── System overview ────────────────────────────────────────────────────────

@router.get("/system")
async def system_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """System health and platform-wide metrics for admin dashboard."""
    await _require_admin(request, db)

    # User stats
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    admin_count = (await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )).scalar() or 0
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar() or 0

    # Request stats
    total_requests = (await db.execute(
        select(func.count()).select_from(InfraRequestRecord)
    )).scalar() or 0

    status_counts = await db.execute(
        select(InfraRequestRecord.status, func.count())
        .group_by(InfraRequestRecord.status)
    )
    by_status = {
        (row[0].value if hasattr(row[0], "value") else row[0]): row[1]
        for row in status_counts
    }

    # Team account stats
    team_count = (await db.execute(
        select(func.count()).select_from(TeamAccount)
    )).scalar() or 0
    active_teams = (await db.execute(
        select(func.count()).select_from(TeamAccount).where(TeamAccount.status == "active")
    )).scalar() or 0

    # Request type breakdown
    type_counts = await db.execute(
        select(InfraRequestRecord.request_type, func.count())
        .group_by(InfraRequestRecord.request_type)
    )
    by_type = {row[0]: row[1] for row in type_counts}

    # Requests this week
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = (await db.execute(
        select(func.count()).select_from(InfraRequestRecord)
        .where(InfraRequestRecord.created_at >= week_ago)
    )).scalar() or 0

    # Event count
    event_count = (await db.execute(
        select(func.count()).select_from(RequestEvent)
    )).scalar() or 0

    return {
        "users": {
            "total": user_count,
            "admins": admin_count,
            "active": active_users,
            "disabled": user_count - active_users,
        },
        "requests": {
            "total": total_requests,
            "by_status": by_status,
            "this_week": recent_count,
        },
        "teams": {
            "total": team_count,
            "active": active_teams,
        },
        "by_type": by_type,
        "events_total": event_count,
    }
