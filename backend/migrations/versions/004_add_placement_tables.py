"""Add placement tables (companies, job_postings, applications, shortlists)

Revision ID: 004
Revises: 
Create Date: 2026-08-17 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '004'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create placement tables."""
    
    # 1. Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_companies_id', 'companies', ['id'])
    op.create_index('ix_companies_name', 'companies', ['name'])

    # 2. Create job_postings table
    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('required_skills', JSONB(), nullable=True),
        sa.Column('experience_level', sa.String(length=50), nullable=True),
        sa.Column('cgpa_criteria', sa.Float(), nullable=True),
        sa.Column('branch_eligibility', JSONB(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('salary_range', sa.String(length=100), nullable=True),
        sa.Column('application_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('drive_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('draft', 'open', 'closed', name='jobstatus'), nullable=True, server_default='open'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_postings_id', 'job_postings', ['id'])
    op.create_index('ix_job_postings_company_id', 'job_postings', ['company_id'])
    op.create_index('ix_job_postings_status', 'job_postings', ['status'])

    # 3. Create applications table
    op.create_table(
        'applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('job_posting_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('applied', 'shortlisted', 'rejected', 'selected', name='applicationstatus'), nullable=True, server_default='applied'),
        sa.Column('eligibility_score', sa.Float(), nullable=True),
        sa.Column('match_percentage', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_applications_id', 'applications', ['id'])
    op.create_index('ix_applications_student_id', 'applications', ['student_id'])
    op.create_index('ix_applications_job_posting_id', 'applications', ['job_posting_id'])

    # 4. Create shortlists table
    op.create_table(
        'shortlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('job_posting_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('shortlisted_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shortlisted_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shortlists_id', 'shortlists', ['id'])
    op.create_index('ix_shortlists_student_id', 'shortlists', ['student_id'])
    op.create_index('ix_shortlists_company_id', 'shortlists', ['company_id'])


def downgrade() -> None:
    """Drop placement tables."""
    
    # Drop in reverse order (to handle foreign keys)
    op.drop_table('shortlists')
    op.drop_table('applications')
    op.drop_table('job_postings')
    op.drop_table('companies')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS jobstatus')
    op.execute('DROP TYPE IF EXISTS applicationstatus')