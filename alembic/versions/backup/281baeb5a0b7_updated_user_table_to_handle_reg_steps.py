"""updated user table to handle reg steps

Revision ID: 281baeb5a0b7
Revises: 9a94073f6d89
Create Date: 2026-01-22 16:19:51.881867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '281baeb5a0b7'
down_revision: Union[str, Sequence[str], None] = '9a94073f6d89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
