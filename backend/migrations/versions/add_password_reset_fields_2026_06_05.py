"""Add password reset token columns to users table

Revision ID: add_password_reset_fields_2026_06_05
Revises: 
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_password_reset_fields_2026_06_05'
down_revision = 'add_ai_models_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('reset_token', sa.String(length=100), nullable=True, unique=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
