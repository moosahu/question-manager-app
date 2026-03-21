"""Add video_explanation to questions table

Revision ID: add_video_explanation
Revises: add_question_video_fields
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_video_explanation'
down_revision = 'add_question_video_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('questions', sa.Column('video_explanation', sa.Text, nullable=True))


def downgrade():
    op.drop_column('questions', 'video_explanation')
