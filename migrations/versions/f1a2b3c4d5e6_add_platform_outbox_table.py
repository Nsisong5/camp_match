"""add platform outbox table

Revision ID: f1a2b3c4d5e6
Revises: d123456789ab
Create Date: 2026-11-07 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'd123456789ab'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'platform_outbox',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'DELIVERED', 'DEAD')", name='check_platform_outbox_status'),
    )
    op.create_index(
        'ix_platform_outbox_pending_next_attempt',
        'platform_outbox',
        ['next_attempt_at'],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        'ix_platform_outbox_status_created',
        'platform_outbox',
        ['status', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_platform_outbox_status_created', table_name='platform_outbox')
    op.drop_index('ix_platform_outbox_pending_next_attempt', table_name='platform_outbox')
    op.drop_table('platform_outbox')
