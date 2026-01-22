"""re-add registration_step to users

Revision ID: 8fd1b9fb99df
Revises: d3b82334a56b
Create Date: 2026-01-22 20:51:38.010080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8fd1b9fb99df'
down_revision: Union[str, Sequence[str], None] = 'd3b82334a56b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("registration_step", sa.String(), nullable=True)
    )



def downgrade() -> None:
    """Downgrade schema."""
    pass
