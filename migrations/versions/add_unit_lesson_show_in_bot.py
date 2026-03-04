"""Add show_in_bot to unit and lesson

Revision ID: add_unit_lesson_show_in_bot
Revises: add_lesson_plan_progress
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_unit_lesson_show_in_bot'
down_revision = 'add_lesson_plan_progress'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('unit', sa.Column('show_in_bot', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('lesson', sa.Column('show_in_bot', sa.Boolean(), server_default='true', nullable=False))


def downgrade():
    op.drop_column('lesson', 'show_in_bot')
    op.drop_column('unit', 'show_in_bot')
