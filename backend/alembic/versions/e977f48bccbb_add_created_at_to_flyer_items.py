"""add_created_at_to_flyer_items

Revision ID: e977f48bccbb
Revises: 8ecb061d86b7
Create Date: 2025-05-06 00:47:11.468664

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e977f48bccbb'
down_revision: Union[str, None] = '8ecb061d86b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('flyer_items', 
                  sa.Column('created_at', 
                            sa.DateTime(timezone=True), 
                            server_default=sa.text('now()'), 
                            nullable=True)
                  )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('flyer_items', 'created_at')
