"""
Add match_snapshot and unique constraint to applications table

Revision ID: 009
Revises: 008
Create Date: 2026-10-10 16:00:00.000000

This migration:
- Adds match_snapshot JSONB column to applications table for immutable application snapshots
- Adds unique constraint uq_applications_student_job on (student_id, job_posting_id) to prevent duplicate applications
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('applications')]

    if 'match_snapshot' not in existing_cols:
        op.add_column(
            'applications',
            sa.Column('match_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )

    # Add unique constraint if not already present
    existing_constraints = [c['name'] for c in inspector.get_unique_constraints('applications')]
    if 'uq_applications_student_job' not in existing_constraints:
        op.create_unique_constraint(
            'uq_applications_student_job',
            'applications',
            ['student_id', 'job_posting_id']
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    existing_constraints = [c['name'] for c in inspector.get_unique_constraints('applications')]
    if 'uq_applications_student_job' in existing_constraints:
        op.drop_constraint('uq_applications_student_job', 'applications', type_='unique')

    existing_cols = [c['name'] for c in inspector.get_columns('applications')]
    if 'match_snapshot' in existing_cols:
        op.drop_column('applications', 'match_snapshot')
