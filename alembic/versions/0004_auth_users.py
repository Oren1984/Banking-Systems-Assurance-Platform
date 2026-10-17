"""auth_users

Revision ID: 0004_auth_users
Revises: a14a5514b9ab
Create Date: 2026-10-17

Additive only: creates the `users` table for authentication/RBAC (auth/).
No existing table, column, or row is altered. Downgrade drops only this
table — it never touches scans, findings, scores, or audit_events (audit
rows reference users by username string, not by foreign key, so they
survive a downgrade unchanged).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_auth_users"
down_revision: Union[str, None] = "a14a5514b9ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded: the UI service layer calls Base.metadata.create_all() (an
    # existing pattern in ui/services/), so a database the new code touched
    # before this migration ran may already have an identical `users` table.
    if sa.inspect(op.get_bind()).has_table("users"):
        return
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
