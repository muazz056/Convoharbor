"""Add ai_models table for super admin model management

Revision ID: add_ai_models_table
Revises: add_pgvector_embeddings
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_ai_models_table'
down_revision = 'add_pgvector_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('model_type', sa.String(length=20), nullable=False, server_default=sa.text("'chat'")),
        sa.Column('context_window', sa.Integer(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_models_provider'), 'ai_models', ['provider'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ai_models_provider'), table_name='ai_models')
    op.drop_table('ai_models')
