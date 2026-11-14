"""add platform jobs table

Revision ID: a1b2c3d4e5f8
Revises: f1a2b3c4d5e6
Create Date: 2026-11-07 13:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f8'
down_revision: str | Sequence[str] | None = 'f1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'platform_jobs',
        sa.Column('name', sa.String(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('interval_seconds', sa.Integer(), nullable=False),
        sa.Column('last_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_holder', sa.String(), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(
        'ix_platform_jobs_enabled_next_run',
        'platform_jobs',
        ['next_run_at'],
        postgresql_where=sa.text('enabled = true'),
    )


def downgrade() -> None:
    op.drop_index('ix_platform_jobs_enabled_next_run', table_name='platform_jobs')
    op.drop_table('platform_jobs')
