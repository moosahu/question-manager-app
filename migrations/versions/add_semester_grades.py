"""add student_semester_grades table

Revision ID: add_semester_grades
Revises:
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_semester_grades'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_semester_grades',
        sa.Column('id',                sa.Integer(),  primary_key=True),
        sa.Column('student_id',        sa.Integer(),  sa.ForeignKey('students.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('period',            sa.Integer(),  nullable=False),
        sa.Column('grade',             sa.Float(),    nullable=False),
        sa.Column('max_grade',         sa.Float(),    nullable=False),
        sa.Column('ai_message',        sa.Text(),     nullable=True),
        sa.Column('notification_sent', sa.Boolean(),  nullable=False, server_default='false'),
        sa.Column('notified_at',       sa.DateTime(), nullable=True),
        sa.Column('created_at',        sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',        sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('student_semester_grades')
