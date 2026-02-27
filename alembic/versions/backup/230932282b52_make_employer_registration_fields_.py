"""make employer registration fields nullable

Revision ID: 230932282b52
Revises: 50325f7c49bc
Create Date: 2026-01-18 16:39:42.582183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '230932282b52'
down_revision: Union[str, Sequence[str], None] = '50325f7c49bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Make fields nullable that should be filled during profile completion
    op.alter_column('employers', 'full_name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'job_title',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'work_email',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'industry',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'company_size',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'location',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    op.alter_column('employers', 'description',
               existing_type=sa.VARCHAR(),
               nullable=True)


def downgrade():
    # Revert back to NOT NULL (will fail if there are null values)
    op.alter_column('employers', 'description',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'location',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'company_size',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'industry',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'work_email',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'job_title',
               existing_type=sa.VARCHAR(),
               nullable=False)
    
    op.alter_column('employers', 'full_name',
               existing_type=sa.VARCHAR(),
               nullable=False)
