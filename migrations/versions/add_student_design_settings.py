"""Add student_design_settings table

Revision ID: add_student_design_settings
Revises: add_user_fcm_token
Create Date: 2026-03-15 23:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_student_design_settings'
down_revision = 'add_user_fcm_token'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_design_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allowed_designs', sa.String(length=200), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('student_design_settings')
