"""Add pgvector extension and document_embeddings table

Revision ID: add_pgvector_embeddings
Revises: add_performance_indexes_2025_11_01
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'add_pgvector_embeddings'
down_revision = 'add_performance_indexes_2025_11_01'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('document_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vector_id', sa.String(length=255), nullable=False),
        sa.Column('doc_id', sa.String(length=36), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_content', sa.Text(), nullable=False),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(length=500), nullable=False),
        sa.Column('chatbot_id', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('embedding_openai', Vector(3072), nullable=True),
        sa.Column('embedding_gemini', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chatbot_id'], ['chatbots.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vector_id')
    )
    op.create_index(op.f('ix_document_embeddings_vector_id'), 'document_embeddings', ['vector_id'], unique=True)
    op.create_index(op.f('ix_document_embeddings_doc_id'), 'document_embeddings', ['doc_id'], unique=False)
    op.create_index(op.f('ix_document_embeddings_source'), 'document_embeddings', ['source'], unique=False)
    op.create_index(op.f('ix_document_embeddings_chatbot_id'), 'document_embeddings', ['chatbot_id'], unique=False)
    op.create_index(op.f('ix_document_embeddings_tenant_id'), 'document_embeddings', ['tenant_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_document_embeddings_tenant_id'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_chatbot_id'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_source'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_doc_id'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_vector_id'), table_name='document_embeddings')
    op.drop_table('document_embeddings')
