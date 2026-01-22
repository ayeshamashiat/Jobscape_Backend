"""updated employer.....AGAIN!

Revision ID: 90221c8d971f
Revises: 230932282b52
Create Date: 2026-01-18 22:24:25.219416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '90221c8d971f'
down_revision: Union[str, Sequence[str], None] = '2878a848255c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
