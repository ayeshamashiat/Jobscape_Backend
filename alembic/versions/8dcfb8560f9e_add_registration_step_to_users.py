"""add registration_step to users

Revision ID: 8dcfb8560f9e
Revises: 281baeb5a0b7
Create Date: 2026-01-22 19:27:50.482004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dcfb8560f9e'
down_revision: Union[str, Sequence[str], None] = '281baeb5a0b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Only add the column - NOTHING ELSE
    op.add_column('users', sa.Column('registration_step', sa.String(), nullable=True))


def downgrade():
    op.drop_column('users', 'registration_step')
