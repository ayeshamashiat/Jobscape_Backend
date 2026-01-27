"""Add saved_cover_letters table

Revision ID: 1db026021340
Revises: 281baeb5a0b7
Create Date: 2026-01-26 20:54:55.991144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1db026021340'
down_revision: Union[str, Sequence[str], None] = '281baeb5a0b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands manually adjusted ###
    op.create_table(
        'saved_cover_letters',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('job_seeker_id', sa.UUID(), sa.ForeignKey('job_seekers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cover_letter_text', sa.TEXT(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    # ### end manual commands ###

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('saved_cover_letters')
