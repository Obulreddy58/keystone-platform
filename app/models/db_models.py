"""
SQLAlchemy ORM models for tracking self-service requests.

Every request that flows through the API gets stored with:
- Full request details (who, what, where)
- PR link, branch, files created
- Status tracking (pending → provisioning → deployed / failed)
- Timestamps for audit trail
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RequestStatus(str, enum.Enum):
    PENDING = "pending"              # PR created, awaiting review
    PLAN_RUNNING = "plan_running"    # terraform plan in progress
    PLAN_FAILED = "plan_failed"      # plan failed
    AWAITING_APPROVAL = "awaiting_approval"  # plan succeeded, needs merge
    PROVISIONING = "provisioning"    # terraform apply running
    DEPLOYED = "deployed"            # apply succeeded
    FAILED = "failed"                # apply failed
    DESTROYED = "destroyed"          # resources torn down
    CANCELLED = "cancelled"          # PR closed without merge


class AccountStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"  # PO submitted, waiting for admin approval
    APPROVED = "approved"                  # Approved, provisioning will start
    PROVISIONING = "provisioning"          # Account creation in progress
    ACTIVE = "active"                      # Account ready, team can request resources
    SUSPENDED = "suspended"                # Temporarily disabled
    CLOSED = "closed"                      # Account closed


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


class User(Base):
    """Portal user account for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    team_name: Mapped[str] = mapped_column(String(100), default="", index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False), default=UserRole.VIEWER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role.value}]>"


class InfraRequestRecord(Base):
    """Tracks every self-service request from Jira form to deployed infra."""

    __tablename__ = "infra_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ─── Identifiers ─────────────────────────────────────────────────────
    jira_ticket_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    request_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False),
        default=RequestStatus.PENDING,
        index=True,
    )

    # ─── Who ─────────────────────────────────────────────────────────────
    requester_email: Mapped[str] = mapped_column(String(255), default="")
    team_name: Mapped[str] = mapped_column(String(100), default="", index=True)
    cost_center: Mapped[str] = mapped_column(String(50), default="")

    # ─── What ────────────────────────────────────────────────────────────
    resource_name: Mapped[str] = mapped_column(String(255), default="")
    environment: Mapped[str] = mapped_column(String(20), default="", index=True)
    account_id: Mapped[str] = mapped_column(String(20), default="")
    request_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ─── Where (GitHub) ──────────────────────────────────────────────────
    github_group: Mapped[str] = mapped_column(String(255), default="")
    github_repo: Mapped[str] = mapped_column(String(255), default="")
    pr_url: Mapped[str] = mapped_column(String(500), default="")
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_name: Mapped[str] = mapped_column(String(255), default="")
    files_created: Mapped[int] = mapped_column(Integer, default=0)
    file_paths: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ─── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Deployment outputs ──────────────────────────────────────────────
    deployment_outputs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────
    events: Mapped[list[RequestEvent]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="RequestEvent.created_at"
    )

    def __repr__(self) -> str:
        return f"<InfraRequest {self.jira_ticket_key} [{self.status.value}]>"


class RequestEvent(Base):
    """
    Timeline of events for a request.
    Every status change, comment, or CI/CD callback creates an event.
    """

    __tablename__ = "request_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("infra_requests.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    request: Mapped[InfraRequestRecord] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<Event {self.event_type} for request#{self.request_id}>"


# ─── Team Account Registry ──────────────────────────────────────────────────


class TeamAccount(Base):
    """
    Registry mapping teams to their AWS accounts.

    When a PO requests an account, a row is created with status=pending_approval.
    After admin approval + provisioning, the status moves to active.
    Subsequent resource requests look up the team's account_id from here.
    """

    __tablename__ = "team_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ─── Team identity ───────────────────────────────────────────────────
    team_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    team_display_name: Mapped[str] = mapped_column(String(255), default="")
    product_owner_email: Mapped[str] = mapped_column(String(255))
    cost_center: Mapped[str] = mapped_column(String(50), default="")
    business_unit: Mapped[str] = mapped_column(String(100), default="")

    # ─── AWS account ─────────────────────────────────────────────────────
    account_id: Mapped[str] = mapped_column(String(20), default="", index=True)
    account_name: Mapped[str] = mapped_column(String(255), default="")
    account_email: Mapped[str] = mapped_column(String(255), default="")
    ou_id: Mapped[str] = mapped_column(String(100), default="")
    environment: Mapped[str] = mapped_column(String(20), default="dev")

    # ─── GitHub ──────────────────────────────────────────────────────────
    github_group: Mapped[str] = mapped_column(String(255), default="")
    github_repo: Mapped[str] = mapped_column(String(255), default="infra")

    # ─── Status ──────────────────────────────────────────────────────────
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False),
        default=AccountStatus.PENDING_APPROVAL,
        index=True,
    )
    is_admin_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str] = mapped_column(String(255), default="")

    # ─── Provisioning state ──────────────────────────────────────────────
    jira_ticket_key: Mapped[str] = mapped_column(String(50), default="", index=True)
    pr_url: Mapped[str] = mapped_column(String(500), default="")
    oidc_role_arn: Mapped[str] = mapped_column(String(500), default="")
    state_bucket: Mapped[str] = mapped_column(String(255), default="")
    provisioning_outputs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<TeamAccount {self.team_name} [{self.status.value}] account={self.account_id}>"
