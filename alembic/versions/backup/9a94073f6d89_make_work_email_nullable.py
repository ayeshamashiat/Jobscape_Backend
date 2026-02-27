"""make work_email nullable

Revision ID: 9a94073f6d89
Revises: 90221c8d971f
Create Date: 2026-01-19 10:41:09.643774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a94073f6d89'
down_revision: Union[str, Sequence[str], None] = '90221c8d971f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('employers', 'work_email',
               existing_type=sa.VARCHAR(),
               nullable=True)  # ← Change to nullable

def downgrade():
    op.alter_column('employers', 'work_email',
               existing_type=sa.VARCHAR(),
               nullable=False)
