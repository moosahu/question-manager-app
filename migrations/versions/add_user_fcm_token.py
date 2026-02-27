"""Add fcm_token column to user table for admin push notifications

Revision ID: add_user_fcm_token
Revises: add_ai_usage_logs
Create Date: 2026-02-27 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_fcm_token'
down_revision = 'add_ai_usage_logs'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fcm_token', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('fcm_token')
