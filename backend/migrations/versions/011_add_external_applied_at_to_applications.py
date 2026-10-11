"""
Add external_applied_at column to applications table

Revision ID: 011
Revises: 010
Create Date: 2026-10-11 00:15:00.000000

This migration:
- Adds external_applied_at TIMESTAMP WITH TIME ZONE nullable column to applications table
- Allows students to record confirmation of submission on external company portals
- Preserves all existing application records and snapshots
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('applications')]

    if 'external_applied_at' not in existing_cols:
        op.add_column(
            'applications',
            sa.Column('external_applied_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('applications')]

    if 'external_applied_at' in existing_cols:
        op.drop_column('applications', 'external_applied_at')
