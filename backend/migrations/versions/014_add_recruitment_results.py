"""
Add recruitment result batches and candidate result items

Revision ID: 014
Revises: 013
Create Date: 2026-10-11 10:35:00.000000

This migration:
- Creates enums for batch status, item review state, and item normalized status
- Creates recruitment_result_batches table
- Creates recruitment_result_items table with JSONB raw_data and match_evidence
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enums if not existing
    batch_status_enum = sa.Enum(
        'uploaded', 'in_review', 'partially_confirmed', 'fully_confirmed', 'archived',
        name='recruitment_result_batch_status'
    )
    batch_status_enum.create(conn, checkfirst=True)

    review_state_enum = sa.Enum(
        'pending', 'matched', 'ambiguous', 'unresolved', 'confirmed', 'ignored',
        name='recruitment_result_review_state'
    )
    review_state_enum.create(conn, checkfirst=True)

    item_status_enum = sa.Enum(
        'shortlisted', 'selected', 'rejected', 'absent', 'on_hold',
        name='recruitment_result_item_status'
    )
    item_status_enum.create(conn, checkfirst=True)

    # 2. Create recruitment_result_batches table
    if 'recruitment_result_batches' not in existing_tables:
        op.create_table(
            'recruitment_result_batches',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('job_posting_id', sa.Integer(), nullable=True),
            sa.Column('circular_id', sa.Integer(), nullable=True),
            sa.Column('file_id', UUID(as_uuid=True), nullable=False),
            sa.Column('round_name', sa.String(length=100), nullable=False),
            sa.Column('round_type', sa.String(length=50), nullable=False, server_default='assessment'),
            sa.Column('is_final_round', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column(
                'status',
                sa.Enum('uploaded', 'in_review', 'partially_confirmed', 'fully_confirmed', 'archived', name='recruitment_result_batch_status', create_type=False),
                nullable=False,
                server_default='in_review'
            ),
            sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('matched_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('ambiguous_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('confirmed_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('uploaded_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['circular_id'], ['recruitment_circulars.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_recruitment_result_batches_id', 'recruitment_result_batches', ['id'])
        op.create_index('ix_recruitment_result_batches_company_id', 'recruitment_result_batches', ['company_id'])
        op.create_index('ix_recruitment_result_batches_job_posting_id', 'recruitment_result_batches', ['job_posting_id'])
        op.create_index('ix_recruitment_result_batches_circular_id', 'recruitment_result_batches', ['circular_id'])
        op.create_index('ix_recruitment_result_batches_file_id', 'recruitment_result_batches', ['file_id'])
        op.create_index('ix_recruitment_result_batches_status', 'recruitment_result_batches', ['status'])
        op.create_index('ix_recruitment_result_batches_uploaded_by', 'recruitment_result_batches', ['uploaded_by'])

    # 3. Create recruitment_result_items table
    if 'recruitment_result_items' not in existing_tables:
        op.create_table(
            'recruitment_result_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('batch_id', sa.Integer(), nullable=False),
            sa.Column('row_index', sa.Integer(), nullable=False),
            sa.Column('source_page', sa.Integer(), nullable=True),
            sa.Column('raw_data', JSONB(), nullable=False),
            sa.Column('extracted_usn', sa.String(length=50), nullable=True),
            sa.Column('extracted_name', sa.String(length=255), nullable=True),
            sa.Column('extracted_email', sa.String(length=255), nullable=True),
            sa.Column('extracted_status_raw', sa.String(length=100), nullable=True),
            sa.Column('extracted_remarks', sa.Text(), nullable=True),
            sa.Column(
                'normalized_status',
                sa.Enum('shortlisted', 'selected', 'rejected', 'absent', 'on_hold', name='recruitment_result_item_status', create_type=False),
                nullable=False,
                server_default='shortlisted'
            ),
            sa.Column('matched_student_id', sa.Integer(), nullable=True),
            sa.Column('match_confidence', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('match_method', sa.String(length=50), nullable=True),
            sa.Column('match_evidence', JSONB(), nullable=True),
            sa.Column(
                'review_status',
                sa.Enum('pending', 'matched', 'ambiguous', 'unresolved', 'confirmed', 'ignored', name='recruitment_result_review_state', create_type=False),
                nullable=False,
                server_default='pending'
            ),
            sa.Column('confirmed_by', sa.Integer(), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('notification_event_key', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['batch_id'], ['recruitment_result_batches.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['matched_student_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('notification_event_key', name='uq_result_item_notification_event_key'),
        )
        op.create_index('ix_recruitment_result_items_id', 'recruitment_result_items', ['id'])
        op.create_index('ix_recruitment_result_items_batch_id', 'recruitment_result_items', ['batch_id'])
        op.create_index('ix_recruitment_result_items_extracted_usn', 'recruitment_result_items', ['extracted_usn'])
        op.create_index('ix_recruitment_result_items_extracted_email', 'recruitment_result_items', ['extracted_email'])
        op.create_index('ix_recruitment_result_items_matched_student_id', 'recruitment_result_items', ['matched_student_id'])
        op.create_index('ix_recruitment_result_items_review_status', 'recruitment_result_items', ['review_status'])
        op.create_index('ix_recruitment_result_items_event_key', 'recruitment_result_items', ['notification_event_key'])
        op.create_index('idx_result_items_batch_review', 'recruitment_result_items', ['batch_id', 'review_status'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'recruitment_result_items' in existing_tables:
        op.drop_table('recruitment_result_items')

    if 'recruitment_result_batches' in existing_tables:
        op.drop_table('recruitment_result_batches')

    # Drop enums
    sa.Enum(name='recruitment_result_item_status').drop(conn, checkfirst=True)
    sa.Enum(name='recruitment_result_review_state').drop(conn, checkfirst=True)
    sa.Enum(name='recruitment_result_batch_status').drop(conn, checkfirst=True)
