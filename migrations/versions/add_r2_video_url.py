"""add r2_video_url to questions

Revision ID: add_r2_video_url
Revises: add_video_explanation
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_r2_video_url'
down_revision = 'add_video_explanation'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('questions',
        sa.Column('r2_video_url', sa.String(500), nullable=True)
    )


def downgrade():
    op.drop_column('questions', 'r2_video_url')
