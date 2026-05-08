"""add_hired_status

Revision ID: 7b9e1c2d3a4f
Revises: f6e03ae8a215
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7b9e1c2d3a4f'
down_revision = 'f6e03ae8a215'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Use raw connection to commit transaction and run ALTER TYPE outside of it
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    
    try:
        connection.execute(sa.text("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'HIRED'"))
    except Exception:
        pass
    
    try:
        connection.execute(sa.text("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'WITHDRAWN'"))
    except Exception:
        pass

def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    pass
