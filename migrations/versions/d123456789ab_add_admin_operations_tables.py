"""add admin operations tables

Revision ID: d123456789ab
Revises: a1b2c3d4e5f7
Create Date: 2026-10-24 05:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd123456789ab'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. admin_issues table
    op.create_table(
        'admin_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('assignee_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('references', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_summary', sa.String(), nullable=True),
        sa.CheckConstraint('version >= 1', name='ck_admin_issues_version_gte_1'),
        sa.CheckConstraint(
            "status <> 'RESOLVED' OR resolution_summary IS NOT NULL",
            name='ck_admin_issues_resolved_summary',
        ),
        sa.UniqueConstraint('created_by', 'idempotency_key', name='uq_admin_issues_created_by_idempotency_key'),
    )
    op.create_index(
        'ix_admin_issues_status_priority_created',
        'admin_issues',
        ['status', 'priority', 'created_at'],
    )
    op.create_index(
        'ix_admin_issues_assignee',
        'admin_issues',
        ['assignee_id'],
        postgresql_where=sa.text('assignee_id IS NOT NULL'),
    )

    # 2. admin_issue_events table
    op.create_table(
        'admin_issue_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index(
        'ix_admin_issue_events_issue_occurred',
        'admin_issue_events',
        ['issue_id', 'occurred_at', 'id'],
    )

    # 3. admin_audit_events table
    op.create_table(
        'admin_audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('outcome_code', sa.String(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "event_type <> 'ACTION_REQUESTED' OR reason IS NOT NULL",
            name='ck_admin_audit_requested_reason',
        ),
        sa.UniqueConstraint('action_id', 'event_type', name='uq_admin_audit_action_id_event_type'),
    )
    op.create_index(
        'ix_admin_audit_occurred_id',
        'admin_audit_events',
        [sa.text('occurred_at DESC'), 'id'],
    )
    op.create_index(
        'ix_admin_audit_actor_occurred',
        'admin_audit_events',
        ['actor_id', 'occurred_at'],
    )
    op.create_index(
        'ix_admin_audit_target',
        'admin_audit_events',
        ['target_type', 'target_id'],
    )
    op.create_index(
        'ix_admin_audit_requested',
        'admin_audit_events',
        ['occurred_at'],
        postgresql_where=sa.text("event_type = 'ACTION_REQUESTED'"),
    )

    # 4. Immutability triggers
    op.execute(
        """
        CREATE OR REPLACE FUNCTION admin_prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is immutable.', TG_TABLE_NAME;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for tbl in ['admin_issue_events', 'admin_audit_events']:
        op.execute(
            f"""
            CREATE TRIGGER prevent_{tbl}_mutation
            BEFORE UPDATE OR DELETE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION admin_prevent_mutation();
            """
        )


def downgrade() -> None:
    for tbl in ['admin_audit_events', 'admin_issue_events']:
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{tbl}_mutation ON {tbl};")
    op.execute("DROP FUNCTION IF EXISTS admin_prevent_mutation();")

    op.drop_table('admin_audit_events')
    op.drop_table('admin_issue_events')
    op.drop_table('admin_issues')
