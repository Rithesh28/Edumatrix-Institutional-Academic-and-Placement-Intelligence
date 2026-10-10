"""
Add preferred_skills column to job_postings table

Revision ID: 008
Revises: 007
Create Date: 2026-10-09 12:00:00.000000

This migration:
- Adds preferred_skills JSONB column to job_postings table
- Supports 80% required / 20% preferred skill matching
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('job_postings')]

    if 'preferred_skills' not in existing_cols:
        op.add_column(
            'job_postings',
            sa.Column('preferred_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]')
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('job_postings')]

    if 'preferred_skills' in existing_cols:
        op.drop_column('job_postings', 'preferred_skills')
