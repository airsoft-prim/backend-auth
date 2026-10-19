"""Create indexes.

Revision ID: 000000000004
Revises: 000000000003
Create Date: 2026-10-19 14:13:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "000000000004"
down_revision: str | Sequence[str] | None = "000000000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
        schema="auth",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_users_email_lower",
        table_name="users",
        schema="auth",
    )
