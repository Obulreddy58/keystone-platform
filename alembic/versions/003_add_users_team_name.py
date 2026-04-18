"""add team_name to users table

Revision ID: 003
Revises: 002
Create Date: 2026-04-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("team_name", sa.String(100), server_default="", nullable=False))
    op.create_index("ix_users_team_name", "users", ["team_name"])


def downgrade() -> None:
    op.drop_index("ix_users_team_name", table_name="users")
    op.drop_column("users", "team_name")
