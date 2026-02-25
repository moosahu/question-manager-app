"""Add trusted_device_token and trusted_device_expires columns to user table

Revision ID: add_trusted_device_columns
Revises: manual_nullable_option_text
Create Date: 2026-02-25 03:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_trusted_device_columns'
down_revision = 'manual_nullable_option_text'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trusted_device_token', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('trusted_device_expires', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('trusted_device_expires')
        batch_op.drop_column('trusted_device_token')
