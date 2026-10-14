"""
Add Study Buddy adaptive study plans and tasks

Revision ID: 018
Revises: 017
Create Date: 2026-10-14 17:30:00.000000

This migration:
- Creates study_buddy_plan_status enum
- Creates study_buddy_plans table for persistent student study plans
- Creates study_buddy_plan_tasks table for syllabus-grounded task tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Enum if not existing
    plan_status_enum = PG_ENUM(
        'ACTIVE', 'COMPLETED', 'ARCHIVED',
        name='study_buddy_plan_status'
    )
    plan_status_enum.create(conn, checkfirst=True)

    # 2. Create study_buddy_plans table
    if 'study_buddy_plans' not in existing_tables:
        op.create_table(
            'study_buddy_plans',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('syllabus_document_id', sa.Integer(), sa.ForeignKey('syllabus_documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('syllabus_version', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_date', sa.Date(), nullable=True),
            sa.Column('daily_budget_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column(
                'status',
                PG_ENUM('ACTIVE', 'COMPLETED', 'ARCHIVED', name='study_buddy_plan_status', create_type=False),
                server_default='ACTIVE',
                nullable=False
            ),
            sa.Column('total_tasks', sa.Integer(), server_default='0', nullable=False),
            sa.Column('completed_tasks', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

        op.create_index('ix_study_buddy_plans_id', 'study_buddy_plans', ['id'])
        op.create_index('ix_study_buddy_plans_student_id', 'study_buddy_plans', ['student_id'])
        op.create_index('ix_study_buddy_plans_subject_id', 'study_buddy_plans', ['subject_id'])
        op.create_index('ix_study_buddy_plans_status', 'study_buddy_plans', ['status'])
        op.create_index('ix_study_buddy_plans_student_status', 'study_buddy_plans', ['student_id', 'status'])
        op.create_index('ix_study_buddy_plans_student_subject', 'study_buddy_plans', ['student_id', 'subject_id'])

    # 3. Create study_buddy_plan_tasks table
    if 'study_buddy_plan_tasks' not in existing_tables:
        op.create_table(
            'study_buddy_plan_tasks',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('plan_id', sa.Integer(), sa.ForeignKey('study_buddy_plans.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('unit_id', sa.Integer(), sa.ForeignKey('syllabus_units.id', ondelete='SET NULL'), nullable=True),
            sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True),
            sa.Column('syllabus_document_id', sa.Integer(), sa.ForeignKey('syllabus_documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('syllabus_version', sa.Integer(), nullable=False),
            sa.Column('estimated_duration_minutes', sa.Integer(), nullable=False, server_default='30'),
            sa.Column('scheduled_date', sa.Date(), nullable=True),
            sa.Column('priority', sa.String(50), nullable=False, server_default='medium'),
            sa.Column('recommendation_reason', sa.String(500), nullable=True),
            sa.Column('task_type', sa.String(50), nullable=False, server_default='concept_study'),
            sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

        op.create_index('ix_study_buddy_plan_tasks_id', 'study_buddy_plan_tasks', ['id'])
        op.create_index('ix_study_buddy_plan_tasks_plan_id', 'study_buddy_plan_tasks', ['plan_id'])
        op.create_index('ix_study_buddy_plan_tasks_is_completed', 'study_buddy_plan_tasks', ['is_completed'])
        op.create_index('ix_study_buddy_plan_tasks_plan_order', 'study_buddy_plan_tasks', ['plan_id', 'order'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'study_buddy_plan_tasks' in existing_tables:
        op.drop_table('study_buddy_plan_tasks')

    if 'study_buddy_plans' in existing_tables:
        op.drop_table('study_buddy_plans')

    # Drop enum
    sa.Enum(name='study_buddy_plan_status').drop(conn, checkfirst=True)
