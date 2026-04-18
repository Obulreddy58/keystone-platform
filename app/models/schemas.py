"""
Pydantic schemas for API responses.
Separate from DB models — these shape the JSON the frontend receives.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    event_type: str
    description: str
    metadata_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestOut(BaseModel):
    """Summary view — used in list endpoints."""

    id: int
    jira_ticket_key: str
    request_type: str
    status: str
    requester_email: str
    team_name: str
    resource_name: str
    environment: str
    account_id: str
    github_group: str
    github_repo: str
    pr_url: str
    files_created: int
    created_at: datetime
    updated_at: datetime
    deployed_at: datetime | None = None
    request_data: dict | None = None

    model_config = {"from_attributes": True}


class RequestDetail(RequestOut):
    """Full detail — includes all fields, file paths, events, outputs."""

    account_id: str
    cost_center: str
    pr_number: int | None = None
    branch_name: str
    file_paths: list[str] | None = None
    request_data: dict | None = None
    deployment_outputs: dict | None = None
    error_message: str | None = None
    events: list[EventOut] = []


class StatsOut(BaseModel):
    """Dashboard statistics."""

    total_requests: int
    deployed: int
    pending: int
    failed: int
    by_type: dict[str, int]
    by_team: dict[str, int]
    by_environment: dict[str, int]
    recent_activity: list[RequestOut]


class StatusUpdate(BaseModel):
    """Payload for CI/CD callbacks to update request status."""

    status: str
    deployment_outputs: dict | None = None
    error_message: str | None = None


# ─── Account / Team Registry schemas ────────────────────────────────────────


class TeamAccountOut(BaseModel):
    """Summary view of a team account."""

    id: int
    team_name: str
    team_display_name: str
    product_owner_email: str
    business_unit: str
    cost_center: str
    account_id: str
    account_name: str
    environment: str
    github_group: str
    github_repo: str
    status: str
    is_admin_approved: bool
    jira_ticket_key: str
    pr_url: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    provisioned_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamAccountDetail(TeamAccountOut):
    """Full detail including provisioning outputs."""

    account_email: str
    ou_id: str
    approved_by: str
    oidc_role_arn: str
    state_bucket: str
    provisioning_outputs: dict | None = None
    error_message: str | None = None


class AccountApproval(BaseModel):
    """Payload for an admin to approve or reject an account request."""

    approved: bool
    approved_by: str
    reason: str = ""


class AccountStatsOut(BaseModel):
    """Dashboard statistics for accounts."""

    total_accounts: int
    active: int
    pending_approval: int
    provisioning: int
    by_business_unit: dict[str, int]
    by_environment: dict[str, int]
