"""
Add recruitment circulars, attachments, and job links

Revision ID: 013
Revises: 012
Create Date: 2026-10-11 08:15:00.000000

This migration:
- Creates recruitment_circular_status enum ('draft', 'published', 'archived')
- Creates recruitment_circulars table
- Creates recruitment_circular_attachments table linking to files
- Creates recruitment_circular_jobs table linking to job_postings with unique constraint
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create recruitment_circular_status enum if not exists
    circular_status_enum = sa.Enum('draft', 'published', 'archived', name='recruitment_circular_status')
    circular_status_enum.create(conn, checkfirst=True)

    # 2. Create recruitment_circulars table
    if 'recruitment_circulars' not in existing_tables:
        op.create_table(
            'recruitment_circulars',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('instructions', sa.Text(), nullable=True),
            sa.Column('application_deadline', sa.DateTime(timezone=True), nullable=True),
            sa.Column('drive_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('branch_eligibility', JSONB(), nullable=True),
            sa.Column('status', sa.Enum('draft', 'published', 'archived', name='recruitment_circular_status', create_type=False), nullable=False, server_default='draft'),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_recruitment_circulars_id', 'recruitment_circulars', ['id'])
        op.create_index('ix_recruitment_circulars_company_id', 'recruitment_circulars', ['company_id'])
        op.create_index('ix_recruitment_circulars_status', 'recruitment_circulars', ['status'])
        op.create_index('ix_recruitment_circulars_created_by', 'recruitment_circulars', ['created_by'])

    # 3. Create recruitment_circular_attachments table
    if 'recruitment_circular_attachments' not in existing_tables:
        op.create_table(
            'recruitment_circular_attachments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('circular_id', sa.Integer(), nullable=False),
            sa.Column('file_id', UUID(as_uuid=True), nullable=False),
            sa.Column('attachment_type', sa.String(length=50), nullable=False, server_default='other'),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['circular_id'], ['recruitment_circulars.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_recruitment_circular_attachments_id', 'recruitment_circular_attachments', ['id'])
        op.create_index('ix_recruitment_circular_attachments_circular_id', 'recruitment_circular_attachments', ['circular_id'])
        op.create_index('ix_recruitment_circular_attachments_file_id', 'recruitment_circular_attachments', ['file_id'])

    # 4. Create recruitment_circular_jobs table
    if 'recruitment_circular_jobs' not in existing_tables:
        op.create_table(
            'recruitment_circular_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('circular_id', sa.Integer(), nullable=False),
            sa.Column('job_posting_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['circular_id'], ['recruitment_circulars.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('circular_id', 'job_posting_id', name='uq_recruitment_circular_job'),
        )
        op.create_index('ix_recruitment_circular_jobs_id', 'recruitment_circular_jobs', ['id'])
        op.create_index('ix_recruitment_circular_jobs_circular_id', 'recruitment_circular_jobs', ['circular_id'])
        op.create_index('ix_recruitment_circular_jobs_job_posting_id', 'recruitment_circular_jobs', ['job_posting_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'recruitment_circular_jobs' in existing_tables:
        op.drop_table('recruitment_circular_jobs')

    if 'recruitment_circular_attachments' in existing_tables:
        op.drop_table('recruitment_circular_attachments')

    if 'recruitment_circulars' in existing_tables:
        op.drop_table('recruitment_circulars')

    # Drop enum
    sa.Enum(name='recruitment_circular_status').drop(conn, checkfirst=True)
