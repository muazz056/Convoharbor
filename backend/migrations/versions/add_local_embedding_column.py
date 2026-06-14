"""Add embedding_local column to document_embeddings for local embeddings

Revision ID: add_local_embedding_column
Revises: add_pgvector_embeddings
Create Date: 2026-06-14

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = 'add_local_embedding_column'
down_revision = 'add_password_reset_fields_2026_06_05'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document_embeddings',
        sa.Column('embedding_local', Vector(384), nullable=True)
    )


def downgrade():
    op.drop_column('document_embeddings', 'embedding_local')
