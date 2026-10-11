"""
Add application_url column to job_postings table

Revision ID: 010
Revises: 009
Create Date: 2026-10-10 23:45:00.000000

This migration:
- Adds application_url VARCHAR(2048) nullable column to job_postings table
- Allows Placement Officers to configure official external company application URLs
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('job_postings')]

    if 'application_url' not in existing_cols:
        op.add_column(
            'job_postings',
            sa.Column('application_url', sa.String(length=2048), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('job_postings')]

    if 'application_url' in existing_cols:
        op.drop_column('job_postings', 'application_url')
