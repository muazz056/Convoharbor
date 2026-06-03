"""Add performance indexes for common queries

Revision ID: add_performance_indexes_2025_11_01
Revises: bff71f0a56a1
Create Date: 2025-11-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_performance_indexes_2025_11_01'
down_revision = 'bff71f0a56a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_conversations_user_id', 'conversations', ['user_id'])
    op.create_index('idx_conversations_updated_at', 'conversations', [sa.text('updated_at DESC')])
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])
    op.create_index('idx_chatbots_tenant_id', 'chatbots', ['tenant_id'])
    op.create_index('idx_datasources_chatbot_id', 'data_sources', ['chatbot_id'])


def downgrade():
    op.drop_index('idx_datasources_chatbot_id')
    op.drop_index('idx_chatbots_tenant_id')
    op.drop_index('idx_messages_created_at')
    op.drop_index('idx_messages_conversation_id')
    op.drop_index('idx_conversations_updated_at')
    op.drop_index('idx_conversations_user_id')
    op.drop_index('idx_users_tenant_id')
