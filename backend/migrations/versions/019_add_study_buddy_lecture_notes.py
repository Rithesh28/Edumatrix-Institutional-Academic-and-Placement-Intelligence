"""
Add Study Buddy lecture notes database foundation

Revision ID: 019
Revises: 018
Create Date: 2026-10-14 21:00:00.000000

This migration:
- Creates study_buddy_lecture_note_status enum (DRAFT, PUBLISHED, ARCHIVED)
- Creates study_buddy_lecture_note_processing_status enum (UPLOADED, PROCESSING, EXTRACTED, FAILED)
- Creates study_buddy_lecture_note_indexing_status enum (NOT_INDEXED, INDEXING, INDEXED, FAILED)
- Creates study_buddy_lecture_notes table for lecturer course notes with optional unit/topic alignment
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM


# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enums if not existing
    note_status_enum = PG_ENUM(
        'DRAFT', 'PUBLISHED', 'ARCHIVED',
        name='study_buddy_lecture_note_status'
    )
    note_status_enum.create(conn, checkfirst=True)

    processing_status_enum = PG_ENUM(
        'UPLOADED', 'PROCESSING', 'EXTRACTED', 'FAILED',
        name='study_buddy_lecture_note_processing_status'
    )
    processing_status_enum.create(conn, checkfirst=True)

    indexing_status_enum = PG_ENUM(
        'NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED',
        name='study_buddy_lecture_note_indexing_status'
    )
    indexing_status_enum.create(conn, checkfirst=True)

    # 2. Create study_buddy_lecture_notes table
    if 'study_buddy_lecture_notes' not in existing_tables:
        op.create_table(
            'study_buddy_lecture_notes',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('uploaded_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('files.id', ondelete='SET NULL'), nullable=True),
            sa.Column('unit_id', sa.Integer(), sa.ForeignKey('syllabus_units.id', ondelete='SET NULL'), nullable=True),
            sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('original_filename', sa.String(255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('minio_bucket', sa.String(100), nullable=False, server_default='lecture-notes'),
            sa.Column('minio_object_key', sa.String(500), nullable=False, unique=True),
            sa.Column(
                'status',
                PG_ENUM('DRAFT', 'PUBLISHED', 'ARCHIVED', name='study_buddy_lecture_note_status', create_type=False),
                server_default='DRAFT',
                nullable=False
            ),
            sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                'processing_status',
                PG_ENUM('UPLOADED', 'PROCESSING', 'EXTRACTED', 'FAILED', name='study_buddy_lecture_note_processing_status', create_type=False),
                server_default='UPLOADED',
                nullable=False
            ),
            sa.Column(
                'indexing_status',
                PG_ENUM('NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED', name='study_buddy_lecture_note_indexing_status', create_type=False),
                server_default='NOT_INDEXED',
                nullable=False
            ),
            sa.Column('extracted_text', sa.Text(), nullable=True),
            sa.Column('extraction_error', sa.Text(), nullable=True),
            sa.Column('extraction_metadata', JSONB(), nullable=True),
            sa.Column('indexed_chunk_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('download_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

        op.create_index('ix_study_buddy_lecture_notes_id', 'study_buddy_lecture_notes', ['id'])
        op.create_index('ix_study_buddy_lecture_notes_subject_id', 'study_buddy_lecture_notes', ['subject_id'])
        op.create_index('ix_study_buddy_lecture_notes_uploaded_by_id', 'study_buddy_lecture_notes', ['uploaded_by_id'])
        op.create_index('ix_study_buddy_lecture_notes_file_id', 'study_buddy_lecture_notes', ['file_id'])
        op.create_index('ix_study_buddy_lecture_notes_unit_id', 'study_buddy_lecture_notes', ['unit_id'])
        op.create_index('ix_study_buddy_lecture_notes_topic_id', 'study_buddy_lecture_notes', ['topic_id'])
        op.create_index('ix_study_buddy_lecture_notes_status', 'study_buddy_lecture_notes', ['status'])
        op.create_index('ix_study_buddy_lecture_notes_is_published', 'study_buddy_lecture_notes', ['is_published'])
        op.create_index('ix_study_buddy_lecture_notes_processing_status', 'study_buddy_lecture_notes', ['processing_status'])
        op.create_index('ix_study_buddy_lecture_notes_indexing_status', 'study_buddy_lecture_notes', ['indexing_status'])
        op.create_index('ix_study_buddy_lecture_notes_subject_status', 'study_buddy_lecture_notes', ['subject_id', 'status'])
        op.create_index('ix_study_buddy_lecture_notes_subject_published', 'study_buddy_lecture_notes', ['subject_id', 'is_published'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'study_buddy_lecture_notes' in existing_tables:
        op.drop_table('study_buddy_lecture_notes')

    # Drop enums safely
    op.execute("DROP TYPE IF EXISTS study_buddy_lecture_note_indexing_status")
    op.execute("DROP TYPE IF EXISTS study_buddy_lecture_note_processing_status")
    op.execute("DROP TYPE IF EXISTS study_buddy_lecture_note_status")
