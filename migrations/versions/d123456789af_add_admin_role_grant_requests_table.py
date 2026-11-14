"""add admin role grant requests table

Revision ID: d123456789af
Revises: d123456789ae
Create Date: 2026-11-08 02:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd123456789af'
down_revision: str | None = 'd123456789ae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'admin_role_grant_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('target_identity_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('requested_by', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('decided_by', sa.Uuid(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name='check_role_request_status'),
        sa.CheckConstraint("role = 'OPERATIONS'", name='check_role_request_role'),
    )
    op.create_index(
        'ix_admin_role_grant_requests_pending',
        'admin_role_grant_requests',
        ['target_identity_id', 'role'],
        postgresql_where=sa.text("status = 'PENDING'"),
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_admin_role_grant_requests_pending', table_name='admin_role_grant_requests')
    op.drop_table('admin_role_grant_requests')
