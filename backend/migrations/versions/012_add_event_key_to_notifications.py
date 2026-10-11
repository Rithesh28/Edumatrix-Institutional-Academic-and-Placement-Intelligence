"""
Add event_key column to notifications table

Revision ID: 012
Revises: 011
Create Date: 2026-10-11 07:15:00.000000

This migration:
- Adds event_key VARCHAR(255) nullable column with unique index to notifications table
- Enables idempotent deduplication of recruitment and institutional notification events
- Preserves all existing legacy notifications without disruption (PostgreSQL allows multiple NULLs in unique indexes)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('notifications')]

    if 'event_key' not in existing_cols:
        op.add_column(
            'notifications',
            sa.Column('event_key', sa.String(length=255), nullable=True)
        )
        op.create_index(
            'ix_notifications_event_key',
            'notifications',
            ['event_key'],
            unique=True
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('notifications')]

    if 'event_key' in existing_cols:
        op.drop_index('ix_notifications_event_key', table_name='notifications')
        op.drop_column('notifications', 'event_key')
