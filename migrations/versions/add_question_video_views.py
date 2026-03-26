"""add question_video_views table

Revision ID: add_question_video_views
Revises:
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_question_video_views'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'question_video_views',
        sa.Column('id',             sa.Integer(), primary_key=True),
        sa.Column('student_id',     sa.Integer(), sa.ForeignKey('students.id',           ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question_id',    sa.Integer(), sa.ForeignKey('questions.question_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('watched_at',     sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('watch_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('video_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed',      sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('view_count',     sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('student_id', 'question_id', name='uq_student_question_view'),
    )


def downgrade():
    op.drop_table('question_video_views')
