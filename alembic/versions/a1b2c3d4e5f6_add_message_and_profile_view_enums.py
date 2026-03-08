"""add_message_and_profile_view_enums

Revision ID: a1b2c3d4e5f6
Revises: 04ec23d7367e
Create Date: 2026-03-08 10:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f67e1055b288'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL ENUM updates cannot be done within a transaction block natively in Alembic using op.execute()
    # unless autocommit is forced, or we just execute it directly. 
    # With SQLAlchemy we can use connection execution options.
    
    # Alembic runs inside a transaction by default. ALTER TYPE ADD VALUE must run outside of a transaction block
    # so we must run it via raw connection or commit/rollback.
    
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))  # Close Alembic's transaction to allow ALTER TYPE
    
    try:
        connection.execute(sa.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'MESSAGE'"))
    except Exception:
        pass
        
    try:
        connection.execute(sa.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'PROFILE_VIEW'"))
    except Exception:
        pass
        

def downgrade() -> None:
    # PostgreSQL does not easily support dropping enum values without recreating the type entirely.
    pass
