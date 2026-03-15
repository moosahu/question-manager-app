"""add design_tester and allowed_designs to students

Revision ID: add_design_tester_columns
Revises: add_trusted_device_columns
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_design_tester_columns'
down_revision = 'add_trusted_device_columns'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('design_tester', sa.Boolean(), nullable=True, server_default='false'))
        batch_op.add_column(sa.Column('allowed_designs', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('allowed_designs')
        batch_op.drop_column('design_tester')
