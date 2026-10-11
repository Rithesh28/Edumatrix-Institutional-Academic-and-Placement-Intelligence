"""
Add recruitment round lifecycle, student progression outcomes, and placement offers

Revision ID: 015
Revises: 014
Create Date: 2026-10-11 12:40:00.000000

This migration:
- Creates enums for round_outcome and offer_acceptance_status
- Creates recruitment_rounds table with unique (job_posting_id, round_number) and check (round_number > 0)
- Creates student_round_outcomes table with unique (application_id, round_id) and source provenance FKs
- Creates placement_offers table with unique application_id, ctc_lpa, and RESTRICT on offer_letter_file_id
- Adds nullable round_id foreign key to recruitment_result_batches
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enums if not existing
    round_outcome_enum = sa.Enum(
        'cleared', 'rejected', 'absent', 'on_hold', 'offered',
        name='round_outcome'
    )
    round_outcome_enum.create(conn, checkfirst=True)

    offer_acceptance_status_enum = sa.Enum(
        'offered', 'accepted', 'declined', 'rescinded',
        name='offer_acceptance_status'
    )
    offer_acceptance_status_enum.create(conn, checkfirst=True)

    # 2. Create recruitment_rounds table
    if 'recruitment_rounds' not in existing_tables:
        op.create_table(
            'recruitment_rounds',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('job_posting_id', sa.Integer(), nullable=False),
            sa.Column('round_number', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('round_type', sa.String(length=50), nullable=False, server_default='assessment'),
            sa.Column('is_final', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('round_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('round_number > 0', name='chk_recruitment_round_number_positive'),
            sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('job_posting_id', 'round_number', name='uq_recruitment_rounds_job_round_number'),
        )
        op.create_index('ix_recruitment_rounds_id', 'recruitment_rounds', ['id'])
        op.create_index('ix_recruitment_rounds_job_posting_id', 'recruitment_rounds', ['job_posting_id'])
        op.create_index('idx_recruitment_rounds_job_number', 'recruitment_rounds', ['job_posting_id', 'round_number'])

    # 3. Create student_round_outcomes table
    if 'student_round_outcomes' not in existing_tables:
        op.create_table(
            'student_round_outcomes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=False),
            sa.Column('round_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column(
                'outcome',
                sa.Enum('cleared', 'rejected', 'absent', 'on_hold', 'offered', name='round_outcome', create_type=False),
                nullable=False,
                server_default='cleared'
            ),
            sa.Column('score', sa.Float(), nullable=True),
            sa.Column('remarks', sa.Text(), nullable=True),
            sa.Column('source_batch_id', sa.Integer(), nullable=True),
            sa.Column('source_item_id', sa.Integer(), nullable=True),
            sa.Column('confirmed_by', sa.Integer(), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['round_id'], ['recruitment_rounds.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['source_batch_id'], ['recruitment_result_batches.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['source_item_id'], ['recruitment_result_items.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('application_id', 'round_id', name='uq_student_round_outcome_app_round'),
        )
        op.create_index('ix_student_round_outcomes_id', 'student_round_outcomes', ['id'])
        op.create_index('ix_student_round_outcomes_application_id', 'student_round_outcomes', ['application_id'])
        op.create_index('ix_student_round_outcomes_round_id', 'student_round_outcomes', ['round_id'])
        op.create_index('ix_student_round_outcomes_student_id', 'student_round_outcomes', ['student_id'])
        op.create_index('idx_round_outcome_student', 'student_round_outcomes', ['student_id'])
        op.create_index('idx_round_outcome_app_round', 'student_round_outcomes', ['application_id', 'round_id'])
        op.create_index('idx_round_outcome_round_outcome', 'student_round_outcomes', ['round_id', 'outcome'])

    # 4. Create placement_offers table
    if 'placement_offers' not in existing_tables:
        op.create_table(
            'placement_offers',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('job_posting_id', sa.Integer(), nullable=False),
            sa.Column('ctc_lpa', sa.Float(), nullable=True),
            sa.Column('designation', sa.String(length=255), nullable=True),
            sa.Column(
                'acceptance_status',
                sa.Enum('offered', 'accepted', 'declined', 'rescinded', name='offer_acceptance_status', create_type=False),
                nullable=False,
                server_default='offered'
            ),
            sa.Column('offer_letter_file_id', UUID(as_uuid=True), nullable=True),
            sa.Column('offer_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('response_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('verified_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['offer_letter_file_id'], ['files.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('application_id', name='uq_placement_offers_application_id'),
        )
        op.create_index('ix_placement_offers_id', 'placement_offers', ['id'])
        op.create_index('ix_placement_offers_application_id', 'placement_offers', ['application_id'])
        op.create_index('ix_placement_offers_student_id', 'placement_offers', ['student_id'])
        op.create_index('ix_placement_offers_job_posting_id', 'placement_offers', ['job_posting_id'])
        op.create_index('idx_placement_offers_student', 'placement_offers', ['student_id'])
        op.create_index('idx_placement_offers_job', 'placement_offers', ['job_posting_id'])
        op.create_index('idx_placement_offers_status', 'placement_offers', ['acceptance_status'])

    # 5. Add nullable round_id column to recruitment_result_batches
    if 'recruitment_result_batches' in existing_tables:
        batch_columns = [col['name'] for col in inspector.get_columns('recruitment_result_batches')]
        if 'round_id' not in batch_columns:
            op.add_column('recruitment_result_batches', sa.Column('round_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                'fk_recruitment_result_batches_round_id',
                'recruitment_result_batches',
                'recruitment_rounds',
                ['round_id'],
                ['id'],
                ondelete='SET NULL'
            )
            op.create_index('ix_recruitment_result_batches_round_id', 'recruitment_result_batches', ['round_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Remove round_id from recruitment_result_batches
    if 'recruitment_result_batches' in existing_tables:
        batch_columns = [col['name'] for col in inspector.get_columns('recruitment_result_batches')]
        if 'round_id' in batch_columns:
            op.drop_constraint('fk_recruitment_result_batches_round_id', 'recruitment_result_batches', type_='foreignkey')
            op.drop_index('ix_recruitment_result_batches_round_id', table_name='recruitment_result_batches')
            op.drop_column('recruitment_result_batches', 'round_id')

    # 2. Drop tables in reverse order of creation
    if 'placement_offers' in existing_tables:
        op.drop_table('placement_offers')

    if 'student_round_outcomes' in existing_tables:
        op.drop_table('student_round_outcomes')

    if 'recruitment_rounds' in existing_tables:
        op.drop_table('recruitment_rounds')

    # 3. Drop enums
    sa.Enum(name='offer_acceptance_status').drop(conn, checkfirst=True)
    sa.Enum(name='round_outcome').drop(conn, checkfirst=True)
