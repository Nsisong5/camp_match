"""add safety tables

Revision ID: 64029e21ee39
Revises: f4dadabc27b6
Create Date: 2026-10-19 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '64029e21ee39'
down_revision: str | Sequence[str] | None = 'f4dadabc27b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. safety_reports
    op.create_table(
        'safety_reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('reporter_id', sa.Uuid(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('subject_type', sa.String(), nullable=False),
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('subject_user_id', sa.Uuid(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=False),
        sa.Column('request_fingerprint', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('reporter_id <> subject_user_id', name='check_safety_report_reporter_not_subject'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reporter_id', 'idempotency_key', name='uq_safety_reporter_idempotency')
    )
    op.create_index(
        'uq_safety_duplicate_open_report',
        'safety_reports',
        ['reporter_id', 'subject_type', 'subject_id', 'category'],
        unique=True,
        postgresql_where=sa.text("status <> 'CLOSED'")
    )
    op.create_index('ix_safety_reports_reporter_created', 'safety_reports', ['reporter_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('ix_safety_reports_queue', 'safety_reports', ['status', 'created_at'], unique=False)

    # 2. safety_cases
    op.create_table(
        'safety_cases',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('subject_user_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_to', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('version >= 1', name='check_safety_case_version'),
        sa.CheckConstraint('cycle >= 1', name='check_safety_case_cycle'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_cases_queue', 'safety_cases', ['status', 'priority', 'created_at'], unique=False)
    op.create_index('ix_safety_cases_assigned', 'safety_cases', ['assigned_to'], unique=False, postgresql_where=sa.text('assigned_to IS NOT NULL'))

    # 3. safety_case_reports
    op.create_table(
        'safety_case_reports',
        sa.Column('report_id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=False),
        sa.Column('linked_by', sa.Uuid(), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['safety_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index('ix_safety_case_reports_case_id', 'safety_case_reports', ['case_id'], unique=False)

    # 4. safety_evidence
    op.create_table(
        'safety_evidence',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('report_id', sa.Uuid(), nullable=False),
        sa.Column('evidence_type', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=True),
        sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('content_sha256', sa.String(), nullable=True),
        sa.Column('collected_by', sa.Uuid(), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('confidentiality', sa.String(), nullable=False),
        sa.CheckConstraint(
            "(evidence_type <> 'MESSAGE_SNAPSHOT') OR (snapshot IS NOT NULL AND content_sha256 IS NOT NULL AND confidentiality = 'RESTRICTED')",
            name='check_safety_evidence_snapshot'
        ),
        sa.ForeignKeyConstraint(['report_id'], ['safety_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_evidence_report_id', 'safety_evidence', ['report_id'], unique=False)

    # 5. safety_notes
    op.create_table(
        'safety_notes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('cited_evidence_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('corrects_note_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind <> 'CORROBORATED_FACT') OR (jsonb_array_length(cited_evidence_ids) > 0)",
            name='check_safety_note_corroborated_fact'
        ),
        sa.ForeignKeyConstraint(['case_id'], ['safety_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['corrects_note_id'], ['safety_notes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_notes_case_created', 'safety_notes', ['case_id', 'created_at'], unique=False)

    # 6. safety_decisions
    op.create_table(
        'safety_decisions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=False),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('decision_type', sa.String(), nullable=False),
        sa.Column('is_final', sa.Boolean(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('cited_evidence_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cited_note_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('decided_by', sa.Uuid(), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['safety_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_decisions_case_decided', 'safety_decisions', ['case_id', 'decided_at'], unique=False)
    op.create_index(
        'uq_safety_case_cycle_final_decision',
        'safety_decisions',
        ['case_id', 'cycle'],
        unique=True,
        postgresql_where=sa.text('is_final = true')
    )

    # 7. safety_enforcement_actions
    op.create_table(
        'safety_enforcement_actions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=False),
        sa.Column('decision_id', sa.Uuid(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('target_user_id', sa.Uuid(), nullable=True),
        sa.Column('target_listing_id', sa.Uuid(), nullable=True),
        sa.Column('target_key', sa.String(), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('proposed_by', sa.Uuid(), nullable=False),
        sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_by', sa.Uuid(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_reason', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reversed_by', sa.Uuid(), nullable=True),
        sa.Column('reversal_reason', sa.Text(), nullable=True),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('attempts >= 0', name='check_safety_enforcement_attempts'),
        sa.CheckConstraint(
            "(action_type = 'LISTING_SUSPENSION' AND target_listing_id IS NOT NULL AND target_user_id IS NULL) OR "
            "(action_type <> 'LISTING_SUSPENSION' AND target_user_id IS NOT NULL AND target_listing_id IS NULL)",
            name='check_safety_enforcement_targets'
        ),
        sa.ForeignKeyConstraint(['case_id'], ['safety_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decision_id'], ['safety_decisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_safety_live_enforcement_action',
        'safety_enforcement_actions',
        ['case_id', 'action_type', 'target_key'],
        unique=True,
        postgresql_where=sa.text("status IN ('PROPOSED', 'APPROVED', 'APPLIED', 'REVERSAL_PENDING')")
    )
    op.create_index(
        'ix_safety_enforcement_due',
        'safety_enforcement_actions',
        ['next_attempt_at'],
        unique=False,
        postgresql_where=sa.text("status IN ('APPROVED', 'REVERSAL_PENDING')")
    )

    # 8. safety_case_events
    op.create_table(
        'safety_case_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('case_id', sa.Uuid(), nullable=True),
        sa.Column('report_id', sa.Uuid(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint('case_id IS NOT NULL OR report_id IS NOT NULL', name='check_safety_event_target'),
        sa.ForeignKeyConstraint(['case_id'], ['safety_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['safety_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_case_events_case_occurred', 'safety_case_events', ['case_id', 'occurred_at', 'id'], unique=False)

    # Immutability Triggers (ADR-149)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION safety_prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is immutable.', TG_TABLE_NAME;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for tbl in ['safety_evidence', 'safety_notes', 'safety_decisions', 'safety_case_events']:
        op.execute(
            f"""
            CREATE TRIGGER prevent_{tbl}_mutation
            BEFORE UPDATE OR DELETE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION safety_prevent_mutation();
            """
        )


def downgrade() -> None:
    for tbl in ['safety_case_events', 'safety_decisions', 'safety_notes', 'safety_evidence']:
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{tbl}_mutation ON {tbl};")
    op.execute("DROP FUNCTION IF EXISTS safety_prevent_mutation();")

    op.drop_table('safety_case_events')
    op.drop_table('safety_enforcement_actions')
    op.drop_table('safety_decisions')
    op.drop_table('safety_notes')
    op.drop_table('safety_evidence')
    op.drop_table('safety_case_reports')
    op.drop_table('safety_cases')
    op.drop_table('safety_reports')
