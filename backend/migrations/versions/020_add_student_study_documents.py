"""
Add Study Buddy student personal documents foundation

Revision ID: 020
Revises: 019
Create Date: 2026-10-15 06:45:00.000000

This migration:
- Creates study_buddy_student_doc_processing_status enum (UPLOADED, PROCESSING, EXTRACTED, FAILED)
- Creates study_buddy_student_doc_indexing_status enum (NOT_INDEXED, INDEXING, INDEXED, FAILED)
- Creates study_buddy_student_documents table for private student-uploaded study documents
- Creates required indexes including scoped duplicate prevention on (student_id, content_hash) WHERE is_active IS TRUE
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ENUM as PG_ENUM


# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enums if not existing
    processing_status_enum = PG_ENUM(
        'UPLOADED', 'PROCESSING', 'EXTRACTED', 'FAILED',
        name='study_buddy_student_doc_processing_status'
    )
    processing_status_enum.create(conn, checkfirst=True)

    indexing_status_enum = PG_ENUM(
        'NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED',
        name='study_buddy_student_doc_indexing_status'
    )
    indexing_status_enum.create(conn, checkfirst=True)

    # 2. Create study_buddy_student_documents table
    if 'study_buddy_student_documents' not in existing_tables:
        op.create_table(
            'study_buddy_student_documents',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('original_filename', sa.String(255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('content_hash', sa.String(64), nullable=False),
            sa.Column('minio_bucket', sa.String(100), nullable=False, server_default='student-documents'),
            sa.Column('minio_object_key', sa.String(500), nullable=False, unique=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column(
                'processing_status',
                PG_ENUM('UPLOADED', 'PROCESSING', 'EXTRACTED', 'FAILED', name='study_buddy_student_doc_processing_status', create_type=False),
                server_default='UPLOADED',
                nullable=False
            ),
            sa.Column('extracted_text', sa.Text(), nullable=True),
            sa.Column('extraction_error', sa.Text(), nullable=True),
            sa.Column('extraction_metadata', JSONB(), nullable=True),
            sa.Column(
                'indexing_status',
                PG_ENUM('NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED', name='study_buddy_student_doc_indexing_status', create_type=False),
                server_default='NOT_INDEXED',
                nullable=False
            ),
            sa.Column('indexed_chunk_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

        op.create_index('ix_study_buddy_student_documents_id', 'study_buddy_student_documents', ['id'])
        op.create_index('ix_study_buddy_student_documents_student_id', 'study_buddy_student_documents', ['student_id'])
        op.create_index('ix_study_buddy_student_documents_subject_id', 'study_buddy_student_documents', ['subject_id'])
        op.create_index('ix_study_buddy_student_documents_content_hash', 'study_buddy_student_documents', ['content_hash'])
        op.create_index('ix_study_buddy_student_documents_is_active', 'study_buddy_student_documents', ['is_active'])
        op.create_index('ix_study_buddy_student_documents_processing_status', 'study_buddy_student_documents', ['processing_status'])
        op.create_index('ix_study_buddy_student_documents_indexing_status', 'study_buddy_student_documents', ['indexing_status'])
        op.create_index('ix_study_buddy_student_docs_student_active', 'study_buddy_student_documents', ['student_id', 'is_active'])
        op.create_index('ix_study_buddy_student_docs_student_subject', 'study_buddy_student_documents', ['student_id', 'subject_id'])
        op.create_index('ix_study_buddy_student_docs_student_hash', 'study_buddy_student_documents', ['student_id', 'content_hash'])
        op.create_index(
            'uq_study_buddy_student_docs_active_hash',
            'study_buddy_student_documents',
            ['student_id', 'content_hash'],
            unique=True,
            postgresql_where=sa.text('is_active IS TRUE')
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'study_buddy_student_documents' in existing_tables:
        op.drop_table('study_buddy_student_documents')

    # Drop enums safely
    op.execute("DROP TYPE IF EXISTS study_buddy_student_doc_indexing_status")
    op.execute("DROP TYPE IF EXISTS study_buddy_student_doc_processing_status")
