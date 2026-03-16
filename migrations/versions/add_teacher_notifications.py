"""add teacher_notifications table

Revision ID: add_teacher_notifications
Revises: add_teacher_student_link
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_teacher_notifications'
down_revision = 'add_teacher_student_link'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'teacher_notifications',
        sa.Column('id',         sa.Integer(),     primary_key=True),
        sa.Column('teacher_id', sa.Integer(),
                  sa.ForeignKey('teachers.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('title',      sa.String(200),   nullable=False),
        sa.Column('message',    sa.Text(),         nullable=False),
        sa.Column('type',       sa.String(50),    nullable=False, server_default='system'),
        sa.Column('is_read',    sa.Boolean(),     nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(),    nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index(
        'ix_teacher_notifications_teacher_id',
        'teacher_notifications',
        ['teacher_id'],
    )
    op.create_index(
        'ix_teacher_notifications_is_read',
        'teacher_notifications',
        ['is_read'],
    )


def downgrade():
    op.drop_index('ix_teacher_notifications_is_read',   table_name='teacher_notifications')
    op.drop_index('ix_teacher_notifications_teacher_id', table_name='teacher_notifications')
    op.drop_table('teacher_notifications')
