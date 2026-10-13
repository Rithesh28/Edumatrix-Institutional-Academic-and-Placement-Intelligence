"""
Add Study Buddy persistent models: subjects, syllabus documents, units, and topics

Revision ID: 016
Revises: 015
Create Date: 2026-10-13 14:00:00.000000

This migration:
- Creates syllabus_processing_status and syllabus_review_status enums
- Creates subjects table with unique (code, department, curriculum_version)
- Creates syllabus_documents table with versioning and publication flags
- Creates syllabus_units table with source page provenance
- Creates syllabus_topics table with ordering and extraction evidence
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM


# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enums if not existing
    processing_status_enum = PG_ENUM(
        'UPLOADED', 'PROCESSING', 'EXTRACTED', 'REVIEW_REQUIRED', 'FAILED',
        name='syllabus_processing_status'
    )
    processing_status_enum.create(conn, checkfirst=True)

    review_status_enum = PG_ENUM(
        'DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED',
        name='syllabus_review_status'
    )
    review_status_enum.create(conn, checkfirst=True)

    # 2. Create subjects table
    if 'subjects' not in existing_tables:
        op.create_table(
            'subjects',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('code', sa.String(50), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('department', sa.String(100), nullable=False),
            sa.Column('semester', sa.Integer(), nullable=True),
            sa.Column('academic_year', sa.String(50), nullable=True),
            sa.Column('curriculum_version', sa.String(50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('code', 'department', 'curriculum_version', name='uq_subject_code_dept_version')
        )
        op.create_index('ix_subjects_code', 'subjects', ['code'])
        op.create_index('ix_subjects_name', 'subjects', ['name'])
        op.create_index('ix_subjects_department', 'subjects', ['department'])
        op.create_index('ix_subjects_is_active', 'subjects', ['is_active'])
        op.create_index('ix_subjects_dept_active', 'subjects', ['department', 'is_active'])

    # 3. Create syllabus_documents table
    if 'syllabus_documents' not in existing_tables:
        op.create_table(
            'syllabus_documents',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('files.id', ondelete='SET NULL'), nullable=True),
            sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('is_latest', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('original_filename', sa.String(255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('minio_bucket', sa.String(100), nullable=False),
            sa.Column('minio_object_key', sa.String(500), nullable=False, unique=True),
            sa.Column('uploaded_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column(
                'processing_status',
                PG_ENUM('UPLOADED', 'PROCESSING', 'EXTRACTED', 'REVIEW_REQUIRED', 'FAILED', name='syllabus_processing_status', create_type=False),
                server_default='UPLOADED',
                nullable=False
            ),
            sa.Column(
                'review_status',
                PG_ENUM('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', name='syllabus_review_status', create_type=False),
                server_default='DRAFT',
                nullable=False
            ),
            sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('published_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('extracted_text', sa.Text(), nullable=True),
            sa.Column('extraction_error', sa.Text(), nullable=True),
            sa.Column('extraction_metadata', JSONB(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('subject_id', 'version', name='uq_syllabus_subject_version')
        )
        op.create_index('ix_syllabus_documents_subject_id', 'syllabus_documents', ['subject_id'])
        op.create_index('ix_syllabus_documents_file_id', 'syllabus_documents', ['file_id'])
        op.create_index('ix_syllabus_documents_uploaded_by_id', 'syllabus_documents', ['uploaded_by_id'])
        op.create_index('ix_syllabus_documents_processing_status', 'syllabus_documents', ['processing_status'])
        op.create_index('ix_syllabus_documents_review_status', 'syllabus_documents', ['review_status'])
        op.create_index('ix_syllabus_documents_is_published', 'syllabus_documents', ['is_published'])
        op.create_index('ix_syllabus_subject_latest', 'syllabus_documents', ['subject_id', 'is_latest'])
        op.create_index('ix_syllabus_published_state', 'syllabus_documents', ['is_published', 'review_status'])

    # 4. Create syllabus_units table
    if 'syllabus_units' not in existing_tables:
        op.create_table(
            'syllabus_units',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('syllabus_documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('unit_number', sa.Integer(), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('order', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('source_page_start', sa.Integer(), nullable=True),
            sa.Column('source_page_end', sa.Integer(), nullable=True),
            sa.Column('source_evidence', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('document_id', 'order', name='uq_syllabus_unit_order')
        )
        op.create_index('ix_syllabus_units_document_id', 'syllabus_units', ['document_id'])
        op.create_index('ix_syllabus_unit_doc_order', 'syllabus_units', ['document_id', 'order'])

    # 5. Create syllabus_topics table
    if 'syllabus_topics' not in existing_tables:
        op.create_table(
            'syllabus_topics',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('unit_id', sa.Integer(), sa.ForeignKey('syllabus_units.id', ondelete='CASCADE'), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('order', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('extracted_text', sa.Text(), nullable=True),
            sa.Column('source_page', sa.Integer(), nullable=True),
            sa.Column('source_evidence', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('unit_id', 'order', name='uq_syllabus_topic_order')
        )
        op.create_index('ix_syllabus_topics_unit_id', 'syllabus_topics', ['unit_id'])
        op.create_index('ix_syllabus_topic_unit_order', 'syllabus_topics', ['unit_id', 'order'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'syllabus_topics' in existing_tables:
        op.drop_table('syllabus_topics')

    if 'syllabus_units' in existing_tables:
        op.drop_table('syllabus_units')

    if 'syllabus_documents' in existing_tables:
        op.drop_table('syllabus_documents')

    if 'subjects' in existing_tables:
        op.drop_table('subjects')

    op.execute("DROP TYPE IF EXISTS syllabus_review_status")
    op.execute("DROP TYPE IF EXISTS syllabus_processing_status")
