"""Add mode and conversation features

Revision ID: add_mode_features_2025_09_28
Revises: add_notifications_2025_09_27
Create Date: 2025-09-28 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_mode_features_2025_09_28'
down_revision = 'add_notifications_2025_09_27'
branch_labels = None
depends_on = None


def upgrade():
    # Add mode field to chatbots table (stored in config JSON, no schema change needed)
    # Add conversation_ended field to conversations table
    op.add_column('conversations', sa.Column('conversation_ended', sa.Boolean(), nullable=True, default=False))
    op.add_column('conversations', sa.Column('ended_at', sa.DateTime(), nullable=True))
    op.add_column('conversations', sa.Column('satisfaction_rating', sa.Integer(), nullable=True))
    op.add_column('conversations', sa.Column('satisfaction_feedback', sa.Text(), nullable=True))


def downgrade():
    # Remove the added columns
    op.drop_column('conversations', 'satisfaction_feedback')
    op.drop_column('conversations', 'satisfaction_rating')
    op.drop_column('conversations', 'ended_at')
    op.drop_column('conversations', 'conversation_ended')
