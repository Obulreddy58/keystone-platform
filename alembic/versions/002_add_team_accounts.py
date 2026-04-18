"""add team_accounts table

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        # Team identity
        sa.Column("team_name", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("team_display_name", sa.String(255), server_default=""),
        sa.Column("product_owner_email", sa.String(255), nullable=False),
        sa.Column("cost_center", sa.String(50), server_default=""),
        sa.Column("business_unit", sa.String(100), server_default=""),
        # AWS account
        sa.Column("account_id", sa.String(20), server_default="", index=True),
        sa.Column("account_name", sa.String(255), server_default=""),
        sa.Column("account_email", sa.String(255), server_default=""),
        sa.Column("ou_id", sa.String(100), server_default=""),
        sa.Column("environment", sa.String(20), server_default="dev"),
        # GitHub
        sa.Column("github_group", sa.String(255), server_default=""),
        sa.Column("github_repo", sa.String(255), server_default="infra"),
        # Status
        sa.Column("status", sa.String(30), index=True, nullable=False, server_default="pending_approval"),
        sa.Column("is_admin_approved", sa.Boolean, server_default="false"),
        sa.Column("approved_by", sa.String(255), server_default=""),
        # Provisioning
        sa.Column("jira_ticket_key", sa.String(50), server_default="", index=True),
        sa.Column("pr_url", sa.String(500), server_default=""),
        sa.Column("oidc_role_arn", sa.String(500), server_default=""),
        sa.Column("state_bucket", sa.String(255), server_default=""),
        sa.Column("provisioning_outputs", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("team_accounts")
