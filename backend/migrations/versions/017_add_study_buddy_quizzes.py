"""
Add Study Buddy quiz attempts and persistence

Revision ID: 017
Revises: 016
Create Date: 2026-10-13 21:00:00.000000

This migration:
- Creates study_buddy_quiz_status enum
- Creates study_buddy_quiz_attempts table for persisting syllabus-grounded
  quiz attempts, snapshots with hidden answer keys, submissions, and scoring
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ENUM as PG_ENUM


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enum if not existing
    quiz_status_enum = PG_ENUM(
        'GENERATED', 'COMPLETED', 'EXPIRED',
        name='study_buddy_quiz_status'
    )
    quiz_status_enum.create(conn, checkfirst=True)

    # 2. Create study_buddy_quiz_attempts table
    if 'study_buddy_quiz_attempts' not in existing_tables:
        op.create_table(
            'study_buddy_quiz_attempts',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('syllabus_document_id', sa.Integer(), sa.ForeignKey('syllabus_documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('syllabus_version', sa.Integer(), nullable=False),
            sa.Column('unit_id', sa.Integer(), sa.ForeignKey('syllabus_units.id', ondelete='SET NULL'), nullable=True),
            sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('difficulty', sa.String(50), nullable=False, server_default='medium'),
            sa.Column('total_questions', sa.Integer(), nullable=False),
            sa.Column('questions_data', JSONB, nullable=False),
            sa.Column(
                'status',
                PG_ENUM('GENERATED', 'COMPLETED', 'EXPIRED', name='study_buddy_quiz_status', create_type=False),
                server_default='GENERATED',
                nullable=False
            ),
            sa.Column('score', sa.Float(), nullable=True),
            sa.Column('max_score', sa.Integer(), nullable=True),
            sa.Column('percentage', sa.Float(), nullable=True),
            sa.Column('student_answers', JSONB, nullable=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

        op.create_index('ix_study_buddy_quiz_attempts_id', 'study_buddy_quiz_attempts', ['id'])
        op.create_index('ix_study_buddy_quiz_attempts_student_id', 'study_buddy_quiz_attempts', ['student_id'])
        op.create_index('ix_study_buddy_quiz_attempts_subject_id', 'study_buddy_quiz_attempts', ['subject_id'])
        op.create_index('ix_study_buddy_quiz_attempts_status', 'study_buddy_quiz_attempts', ['status'])
        op.create_index('ix_quiz_attempts_student_subject', 'study_buddy_quiz_attempts', ['student_id', 'subject_id'])
        op.create_index('ix_quiz_attempts_student_status', 'study_buddy_quiz_attempts', ['student_id', 'status'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'study_buddy_quiz_attempts' in existing_tables:
        op.drop_table('study_buddy_quiz_attempts')

    # Drop enum
    sa.Enum(name='study_buddy_quiz_status').drop(conn, checkfirst=True)
