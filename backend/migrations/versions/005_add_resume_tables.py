"""
Add resume tables for AI Resume Analyzer

Revision ID: 005
Revises: 004
Create Date: 2026-08-17 00:00:00.000000

This migration creates:
- resumes table
- resume_status enum type
- All indexes and foreign keys
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create resume tables."""
    
    # ============================================
    # 1. Create resume_status enum
    # ============================================
    op.execute("""
        CREATE TYPE resume_status AS ENUM (
            'pending',
            'processing',
            'completed',
            'failed'
        )
    """)
    
    # ============================================
    # 2. Create resumes table
    # ============================================
    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('file_id', UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('skills', JSONB(), nullable=True, server_default='[]'),
        sa.Column('education', JSONB(), nullable=True, server_default='[]'),
        sa.Column('experience', JSONB(), nullable=True, server_default='[]'),
        sa.Column('projects', JSONB(), nullable=True, server_default='[]'),
        sa.Column('certifications', JSONB(), nullable=True, server_default='[]'),
        sa.Column('internships', JSONB(), nullable=True, server_default='[]'),
        sa.Column('additional_data', JSONB(), nullable=True, server_default='{}'),
        sa.Column('ats_score', sa.Float(), nullable=True),
        sa.Column('suggestions', JSONB(), nullable=True, server_default='[]'),
        sa.Column('skill_gap', JSONB(), nullable=True, server_default='[]'),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='resume_status'), 
                  nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # ============================================
    # 3. Create indexes
    # ============================================
    op.create_index('ix_resumes_id', 'resumes', ['id'])
    op.create_index('ix_resumes_student_id', 'resumes', ['student_id'])
    op.create_index('ix_resumes_file_id', 'resumes', ['file_id'])
    op.create_index('ix_resumes_student_status', 'resumes', ['student_id', 'status'])
    op.create_index('ix_resumes_created_at', 'resumes', ['created_at'])
    op.create_index('ix_resumes_ats_score', 'resumes', ['ats_score'])
    op.create_index('ix_resumes_status', 'resumes', ['status'])


def downgrade() -> None:
    """Drop resume tables."""
    
    # Drop indexes first
    op.drop_index('ix_resumes_status', table_name='resumes')
    op.drop_index('ix_resumes_ats_score', table_name='resumes')
    op.drop_index('ix_resumes_created_at', table_name='resumes')
    op.drop_index('ix_resumes_student_status', table_name='resumes')
    op.drop_index('ix_resumes_file_id', table_name='resumes')
    op.drop_index('ix_resumes_student_id', table_name='resumes')
    op.drop_index('ix_resumes_id', table_name='resumes')
    
    # Drop table
    op.drop_table('resumes')
    
    # Drop enum
    op.execute("DROP TYPE resume_status")