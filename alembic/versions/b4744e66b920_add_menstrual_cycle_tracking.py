"""add_menstrual_cycle_tracking

Revision ID: b4744e66b920
Revises: ba4b6f7c83e3
Create Date: 2025-12-26 17:47:20.412519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4744e66b920'
down_revision: Union[str, None] = 'ba4b6f7c83e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create menstrual_cycle_logs table
    op.create_table(
        "menstrual_cycle_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_period_day", sa.Boolean, default=False),
        sa.Column("flow_intensity", sa.String(20), nullable=True),  # spotting, light, medium, heavy
        sa.Column("symptoms", postgresql.JSON, nullable=True),  # Array of symptom strings
        sa.Column("mood", sa.Integer, nullable=True),  # 1-5 scale
        sa.Column("energy_level", sa.Integer, nullable=True),  # 1-5 scale
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "date", name="uq_user_cycle_date"),
    )

    # Create menstrual_cycle_settings table
    op.create_table(
        "menstrual_cycle_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("average_cycle_length", sa.Integer, default=28),
        sa.Column("average_period_length", sa.Integer, default=5),
        sa.Column("last_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notify_period_reminder", sa.Boolean, default=True),
        sa.Column("reminder_days_before", sa.Integer, default=2),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create indexes for faster queries
    op.create_index(
        "ix_menstrual_cycle_logs_user_date",
        "menstrual_cycle_logs",
        ["user_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_menstrual_cycle_logs_user_date")
    op.drop_table("menstrual_cycle_settings")
    op.drop_table("menstrual_cycle_logs")
