"""add provider webhook events table

Revision ID: 13d6ff9f4f3c
Revises: 3f03100cd4d4
Create Date: 2026-10-15 04:40:06.872305

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '13d6ff9f4f3c'
down_revision: str | Sequence[str] | None = '3f03100cd4d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'provider_webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('provider_event_id', sa.String(), nullable=False, unique=True),
        sa.Column('raw_payload_digest', sa.String(), nullable=False),
        sa.Column('normalized_event_type', sa.String(), nullable=False),
        sa.Column('correlated_attempt_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('processing_status', sa.String(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "processing_status IN ('RECEIVED', 'PROCESSED', 'IGNORED_DUPLICATE', 'FAILED_VALIDATION', 'UNCORRELATED')",
            name='check_webhook_processing_status',
        ),
    )
    op.create_index('ix_provider_webhook_events_provider_event_id', 'provider_webhook_events', ['provider_event_id'], unique=True)
    op.create_index('ix_provider_webhook_events_correlated_attempt_id', 'provider_webhook_events', ['correlated_attempt_id'], postgresql_where=sa.text('correlated_attempt_id IS NOT NULL'))
    op.create_index('ix_provider_webhook_events_processing_status', 'provider_webhook_events', ['processing_status'])


def downgrade() -> None:
    op.drop_table('provider_webhook_events')
