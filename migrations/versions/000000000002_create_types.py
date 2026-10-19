"""Create types.

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-10-19 14:11:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "000000000002"
down_revision: str | Sequence[str] | None = "000000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE = postgresql.ENUM("admin", "moderator", "user", name="user_role", schema="auth")


def upgrade() -> None:
    """Upgrade schema."""
    USER_ROLE.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Downgrade schema."""
    USER_ROLE.drop(op.get_bind(), checkfirst=False)
