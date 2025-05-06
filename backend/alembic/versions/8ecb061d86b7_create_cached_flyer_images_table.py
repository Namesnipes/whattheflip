"""create_cached_flyer_images_table

Revision ID: 8ecb061d86b7
Revises: 8db465195c95
Create Date: 2025-05-06 07:15:08.326691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ecb061d86b7'
down_revision: Union[str, None] = '8db465195c95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cached_flyer_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('flipp_flyer_id', sa.Integer(), nullable=False),
        sa.Column('merchant_name', sa.String(), nullable=False),
        sa.Column('image_path', sa.String(), nullable=False),
        sa.Column('postal_code', sa.String(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('flipp_flyer_id'),
        sa.UniqueConstraint('image_path')
    )
    op.create_index(op.f('ix_cached_flyer_images_id'), 'cached_flyer_images', ['id'], unique=False)
    op.create_index(op.f('ix_cached_flyer_images_flipp_flyer_id'), 'cached_flyer_images', ['flipp_flyer_id'], unique=True)
    op.create_index(op.f('ix_cached_flyer_images_merchant_name'), 'cached_flyer_images', ['merchant_name'], unique=False)
    op.create_index(op.f('ix_cached_flyer_images_postal_code'), 'cached_flyer_images', ['postal_code'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_cached_flyer_images_postal_code'), table_name='cached_flyer_images')
    op.drop_index(op.f('ix_cached_flyer_images_merchant_name'), table_name='cached_flyer_images')
    op.drop_index(op.f('ix_cached_flyer_images_flipp_flyer_id'), table_name='cached_flyer_images')
    op.drop_index(op.f('ix_cached_flyer_images_id'), table_name='cached_flyer_images')
    op.drop_table('cached_flyer_images')
