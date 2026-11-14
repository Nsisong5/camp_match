"""add identity verification and google tables

Revision ID: b1b2c3d4e5fa
Revises: ac6bcbcf1bb7
Create Date: 2026-11-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1b2c3d4e5fa'
down_revision: Union[str, Sequence[str], None] = 'ac6bcbcf1bb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Alter identity_accounts table
    op.alter_column('identity_accounts', 'password_hash', existing_type=sa.String(), nullable=True)
    op.add_column('identity_accounts', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('identity_accounts', sa.Column('email_verification_source', sa.String(length=20), nullable=True))

    op.create_check_constraint(
        'check_email_verification_source_valid',
        'identity_accounts',
        "email_verification_source IS NULL OR email_verification_source IN ('OTP', 'GOOGLE', 'LEGACY')"
    )
    op.create_check_constraint(
        'check_email_verification_both_or_neither',
        'identity_accounts',
        "(email_verified_at IS NULL) = (email_verification_source IS NULL)"
    )

    # 2. Backfill pre-existing rows
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE identity_accounts SET email_verified_at = created_at, email_verification_source = 'LEGACY' WHERE email_verified_at IS NULL"
        )
    )

    # 3. Create identity_external_identities table
    op.create_table(
        'identity_external_identities',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('email_at_link', sa.String(length=254), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("provider = 'GOOGLE'", name='check_external_identity_provider_valid'),
        sa.ForeignKeyConstraint(['account_id'], ['identity_accounts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'subject', name='uq_identity_external_identities_provider_subject'),
        sa.UniqueConstraint('account_id', 'provider', name='uq_identity_external_identities_account_provider')
    )
    op.create_index(op.f('ix_identity_external_identities_account_id'), 'identity_external_identities', ['account_id'], unique=False)

    # 4. Create identity_one_time_codes table
    op.create_table(
        'identity_one_time_codes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose = 'EMAIL_VERIFICATION'", name='check_otp_purpose_valid'),
        sa.ForeignKeyConstraint(['account_id'], ['identity_accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_identity_one_time_codes_account_id'), 'identity_one_time_codes', ['account_id'], unique=False)
    op.create_index('ix_identity_otp_account_purpose_issued', 'identity_one_time_codes', ['account_id', 'purpose', 'issued_at'], unique=False)

    # Partial unique index for active codes
    op.execute(
        "CREATE UNIQUE INDEX uq_identity_one_time_codes_active ON identity_one_time_codes (account_id, purpose) WHERE consumed_at IS NULL AND invalidated_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    # Guard check: refuse while passwordless accounts exist
    count = bind.execute(
        sa.text("SELECT count(*) FROM identity_accounts WHERE password_hash IS NULL")
    ).scalar()
    if count and count > 0:
        raise RuntimeError("Cannot downgrade while passwordless accounts exist.")

    op.execute("DROP INDEX IF EXISTS uq_identity_one_time_codes_active")
    op.drop_index('ix_identity_otp_account_purpose_issued', table_name='identity_one_time_codes')
    op.drop_index(op.f('ix_identity_one_time_codes_account_id'), table_name='identity_one_time_codes')
    op.drop_table('identity_one_time_codes')

    op.drop_index(op.f('ix_identity_external_identities_account_id'), table_name='identity_external_identities')
    op.drop_table('identity_external_identities')

    op.drop_constraint('check_email_verification_both_or_neither', 'identity_accounts', type_='check')
    op.drop_constraint('check_email_verification_source_valid', 'identity_accounts', type_='check')
    op.drop_column('identity_accounts', 'email_verification_source')
    op.drop_column('identity_accounts', 'email_verified_at')
    op.alter_column('identity_accounts', 'password_hash', existing_type=sa.String(), nullable=False)
