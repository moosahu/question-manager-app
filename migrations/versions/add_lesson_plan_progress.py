"""Add progress_message and needs_review to lesson_plans

Revision ID: add_lesson_plan_progress
Revises: add_lesson_plan_enhancements
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_lesson_plan_progress'
down_revision = 'add_lesson_plan_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('lesson_plans', sa.Column('progress_message', sa.Text(), nullable=True))
    op.add_column('lesson_plans', sa.Column('needs_review', sa.Boolean(), server_default='false'))
    op.add_column('lesson_plans', sa.Column('include_support_plan', sa.Boolean(), server_default='false'))


def downgrade():
    op.drop_column('lesson_plans', 'include_support_plan')
    op.drop_column('lesson_plans', 'needs_review')
    op.drop_column('lesson_plans', 'progress_message')
