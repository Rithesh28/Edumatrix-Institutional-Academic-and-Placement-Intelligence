"""
Add AI chat support fields to chat_messages table

Revision ID: 007
Revises: 006
Create Date: 2026-10-07 00:00:00.000000

This migration:
- Makes sender_id and receiver_id nullable in chat_messages (to support AI participant)
- Adds is_ai flag and index
- Adds ai_participant identifier
- Adds intent and intent_confidence columns
- Adds sentiment and sentiment_confidence columns
- Adds ai_metadata JSON column
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('chat_messages')]

    # 1. Allow sender_id and receiver_id to be NULL for AI messages
    op.alter_column('chat_messages', 'sender_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('chat_messages', 'receiver_id', existing_type=sa.Integer(), nullable=True)

    # 2. Add AI support columns if not present
    if 'is_ai' not in existing_cols:
        op.add_column('chat_messages', sa.Column('is_ai', sa.Boolean(), nullable=False, server_default='false'))
    if 'ai_participant' not in existing_cols:
        op.add_column('chat_messages', sa.Column('ai_participant', sa.String(length=50), nullable=True))
    if 'intent' not in existing_cols:
        op.add_column('chat_messages', sa.Column('intent', sa.String(length=50), nullable=True))
    if 'intent_confidence' not in existing_cols:
        op.add_column('chat_messages', sa.Column('intent_confidence', sa.Float(), nullable=True))
    if 'sentiment' not in existing_cols:
        op.add_column('chat_messages', sa.Column('sentiment', sa.String(length=50), nullable=True))
    if 'sentiment_confidence' not in existing_cols:
        op.add_column('chat_messages', sa.Column('sentiment_confidence', sa.Float(), nullable=True))
    if 'ai_metadata' not in existing_cols:
        op.add_column('chat_messages', sa.Column('ai_metadata', sa.JSON(), nullable=True))

    # 3. Create index for fast filtering of AI messages if not present
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('chat_messages')]
    if 'ix_chat_messages_is_ai' not in existing_indexes:
        op.create_index(op.f('ix_chat_messages_is_ai'), 'chat_messages', ['is_ai'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_is_ai'), table_name='chat_messages')
    op.drop_column('chat_messages', 'ai_metadata')
    op.drop_column('chat_messages', 'sentiment_confidence')
    op.drop_column('chat_messages', 'sentiment')
    op.drop_column('chat_messages', 'intent_confidence')
    op.drop_column('chat_messages', 'intent')
    op.drop_column('chat_messages', 'ai_participant')
    op.drop_column('chat_messages', 'is_ai')
    op.alter_column('chat_messages', 'receiver_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('chat_messages', 'sender_id', existing_type=sa.Integer(), nullable=False)
