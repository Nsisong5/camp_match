"""add messaging restrictions table

Revision ID: f82b94a10c2f
Revises: e8ea40990a9f
Create Date: 2026-10-19 22:00:00.000000

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = 'f82b94a10c2f'
down_revision: str | Sequence[str] | None = 'e8ea40990a9f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'messaging_restrictions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_reference', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('lifted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'LIFTED')", name='check_messaging_restriction_status'),
        sa.PrimaryKeyConstraint('id', name=op.f('messaging_restrictions_pkey')),
        sa.UniqueConstraint('source_reference', name=op.f('uq_messaging_restriction_source_reference'))
    )
    op.create_index('ix_messaging_restrictions_user_active', 'messaging_restrictions', ['user_id'], unique=False, postgresql_where="(status = 'ACTIVE')")


def downgrade() -> None:
    op.drop_index('ix_messaging_restrictions_user_active', table_name='messaging_restrictions', postgresql_where="(status = 'ACTIVE')")
    op.drop_table('messaging_restrictions')
