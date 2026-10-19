"""
Add job_posting_attachments table for multiple persistent job documents

Revision ID: 022
Revises: 021
Create Date: 2026-10-18 23:15:00.000000

This migration:
- Creates the job_posting_attachments table to support multiple persistent documents per job posting
- Links job_posting_id (CASCADE) and file_id (CASCADE)
- Adds a unique constraint on (job_posting_id, file_id) to prevent duplicate attachments
- Backfills existing job_postings.file_id entries into job_posting_attachments
- Provides clean, reversible downgrade()
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'job_posting_attachments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('job_posting_id', sa.Integer(), sa.ForeignKey('job_postings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('job_posting_id', 'file_id', name='uq_job_posting_file')
    )
    op.create_index('ix_job_posting_attachments_job_posting_id', 'job_posting_attachments', ['job_posting_id'])
    op.create_index('ix_job_posting_attachments_file_id', 'job_posting_attachments', ['file_id'])

    # Seed existing job_postings.file_id references into job_posting_attachments if any exist
    op.execute("""
        INSERT INTO job_posting_attachments (job_posting_id, file_id, display_order, created_at)
        SELECT id, file_id, 0, NOW()
        FROM job_postings
        WHERE file_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_index('ix_job_posting_attachments_file_id', table_name='job_posting_attachments')
    op.drop_index('ix_job_posting_attachments_job_posting_id', table_name='job_posting_attachments')
    op.drop_table('job_posting_attachments')
