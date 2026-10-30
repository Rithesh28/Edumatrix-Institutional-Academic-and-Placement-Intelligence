"""
Add chat_type column to chat_messages table

Revision ID: 023
Revises: 022
Create Date: 2026-10-29 00:00:00.000000

This migration adds the chat_type column that the ChatMessage model expects
but is missing from the database schema.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('chat_messages')]

    # Add chat_type column if not already present
    if 'chat_type' not in existing_cols:
        op.add_column('chat_messages', sa.Column(
            'chat_type',
            sa.String(length=50),
            server_default='human',
            nullable=False
        ))
        # Create index for fast filtering by chat type
        op.create_index(
            op.f('ix_chat_messages_chat_type'),
            'chat_messages',
            ['chat_type'],
            unique=False
        )


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_chat_type'), table_name='chat_messages')
    op.drop_column('chat_messages', 'chat_type')