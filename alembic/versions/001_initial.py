"""create infra_requests and request_events tables

Revision ID: 001
Revises:
Create Date: 2026-04-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "infra_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("jira_ticket_key", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("request_type", sa.String(50), index=True, nullable=False),
        sa.Column("status", sa.String(30), index=True, nullable=False, server_default="pending"),
        sa.Column("requester_email", sa.String(255), server_default=""),
        sa.Column("team_name", sa.String(100), index=True, server_default=""),
        sa.Column("cost_center", sa.String(50), server_default=""),
        sa.Column("resource_name", sa.String(255), server_default=""),
        sa.Column("environment", sa.String(20), index=True, server_default=""),
        sa.Column("account_id", sa.String(20), server_default=""),
        sa.Column("request_data", JSONB, nullable=True),
        sa.Column("github_group", sa.String(255), server_default=""),
        sa.Column("github_repo", sa.String(255), server_default=""),
        sa.Column("pr_url", sa.String(500), server_default=""),
        sa.Column("pr_number", sa.Integer, nullable=True),
        sa.Column("branch_name", sa.String(255), server_default=""),
        sa.Column("files_created", sa.Integer, server_default="0"),
        sa.Column("file_paths", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployment_outputs", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    op.create_table(
        "request_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "request_id",
            sa.Integer,
            sa.ForeignKey("infra_requests.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("request_events")
    op.drop_table("infra_requests")
