"""Add website tracking to conversations

Revision ID: add_website_tracking_2025_09_22
Revises: 01ce30bb6d9a
Create Date: 2025-09-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_website_tracking_2025_09_22'
down_revision = '01ce30bb6d9a'
branch_labels = None
depends_on = None

def upgrade():
    # Add website tracking columns to conversations table (nullable for backward compatibility)
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_domain', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('source_url', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('source_platform', sa.String(length=50), server_default='web', nullable=True))
        batch_op.add_column(sa.Column('source_metadata', sa.JSON(), nullable=True))
        
        # Add indexes for better query performance
        batch_op.create_index('ix_conversations_source_domain', ['source_domain'])
        batch_op.create_index('ix_conversations_source_platform', ['source_platform'])

def downgrade():
    # Remove website tracking columns
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_index('ix_conversations_source_platform')
        batch_op.drop_index('ix_conversations_source_domain')
        batch_op.drop_column('source_metadata')
        batch_op.drop_column('source_platform')
        batch_op.drop_column('source_url')
        batch_op.drop_column('source_domain')
