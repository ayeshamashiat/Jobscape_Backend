"""remove registration step field

Revision ID: d3b82334a56b
Revises: 8dcfb8560f9e
Create Date: 2026-01-22 19:59:34.779993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3b82334a56b'
down_revision: Union[str, Sequence[str], None] = '8dcfb8560f9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Remove registration_step column from users table
    op.drop_column('users', 'registration_step')
    
    # Drop the enum type if it exists (PostgreSQL-specific)
    op.execute("DROP TYPE IF EXISTS registrationstep CASCADE")


def downgrade():
    # Recreate enum type
    op.execute("""
        CREATE TYPE registrationstep AS ENUM (
            'ACCOUNT_CREATED', 
            'EMAIL_VERIFIED', 
            'PROFILE_COMPLETED'
        )
    """)
    
    # Add column back
    op.add_column('users', 
        sa.Column('registration_step', 
                  sa.Enum('ACCOUNT_CREATED', 'EMAIL_VERIFIED', 'PROFILE_COMPLETED', 
                          name='registrationstep'),
                  nullable=False,
                  server_default='ACCOUNT_CREATED')
    )