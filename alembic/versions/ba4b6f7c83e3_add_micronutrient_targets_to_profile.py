"""add_micronutrient_targets_to_profile

Revision ID: ba4b6f7c83e3
Revises: 8872e084e65e
Create Date: 2025-12-26 17:39:14.602979

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba4b6f7c83e3'
down_revision: Union[str, None] = '8872e084e65e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add micronutrient target columns to user_profiles
    op.add_column('user_profiles', sa.Column('daily_sugar_target_g', sa.Float(), nullable=True, server_default='50'))
    op.add_column('user_profiles', sa.Column('daily_fiber_target_g', sa.Float(), nullable=True, server_default='28'))
    op.add_column('user_profiles', sa.Column('daily_sodium_target_mg', sa.Float(), nullable=True, server_default='2300'))
    op.add_column('user_profiles', sa.Column('daily_saturated_fat_target_g', sa.Float(), nullable=True, server_default='20'))


def downgrade() -> None:
    # Remove micronutrient target columns from user_profiles
    op.drop_column('user_profiles', 'daily_saturated_fat_target_g')
    op.drop_column('user_profiles', 'daily_sodium_target_mg')
    op.drop_column('user_profiles', 'daily_fiber_target_g')
    op.drop_column('user_profiles', 'daily_sugar_target_g')
