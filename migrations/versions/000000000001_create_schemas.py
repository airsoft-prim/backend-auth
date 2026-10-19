"""Create schemas.

Revision ID: 000000000001
Revises:
Create Date: 2026-10-19 14:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA auth")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SCHEMA auth")
