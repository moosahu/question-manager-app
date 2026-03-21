"""Add video_url and video_status to questions table

Revision ID: add_question_video_fields
Revises: add_user_fcm_token
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_question_video_fields'
down_revision = 'add_user_fcm_token'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('questions', sa.Column('video_url', sa.String(500), nullable=True))
    op.add_column('questions', sa.Column('video_status', sa.String(20), server_default='none', nullable=True))


def downgrade():
    op.drop_column('questions', 'video_status')
    op.drop_column('questions', 'video_url')
