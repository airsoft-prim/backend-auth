"""Create tables.

Revision ID: 000000000003
Revises: 000000000002
Create Date: 2026-10-19 14:12:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "000000000003"
down_revision: str | Sequence[str] | None = "000000000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Тип создан ревизией 000000000002: create_type=False запрещает повторное CREATE TYPE.
USER_ROLE = postgresql.ENUM(
    "admin", "moderator", "user", name="user_role", schema="auth", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("pswd_hash", sa.String(length=255), nullable=False),
        sa.Column("last_pswd_change", sa.DateTime(timezone=True), nullable=True),
        sa.Column("system_role", USER_ROLE, server_default="user", nullable=False),
        sa.Column("disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
        schema="auth",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users", schema="auth")
