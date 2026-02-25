"""Add textbooks, lesson_pages and lesson_plans tables

Revision ID: add_textbooks_and_lesson_plans
Revises: add_trusted_device_columns
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_textbooks_and_lesson_plans'
down_revision = 'add_trusted_device_columns'
branch_labels = None
depends_on = None


def upgrade():
    # جدول الكتب الدراسية
    op.create_table('textbooks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('course.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('edition_year', sa.String(10), nullable=True),
        sa.Column('pdf_url', sa.Text(), nullable=False),
        sa.Column('total_pages', sa.Integer(), default=0),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )

    # ربط الدروس بصفحات الكتاب
    op.create_table('lesson_pages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lesson_id', sa.Integer(), sa.ForeignKey('lesson.id', ondelete='CASCADE'), nullable=False),
        sa.Column('textbook_id', sa.Integer(), sa.ForeignKey('textbooks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_page', sa.Integer(), nullable=False),
        sa.Column('end_page', sa.Integer(), nullable=False),
        sa.UniqueConstraint('lesson_id', 'textbook_id', name='unique_lesson_textbook'),
    )

    # حفظ التحاضير
    op.create_table('lesson_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lesson_id', sa.Integer(), sa.ForeignKey('lesson.id'), nullable=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=True),
        sa.Column('plan_type', sa.String(30), nullable=False, server_default='single_lesson'),
        sa.Column('ai_provider', sa.String(20), server_default='gemini'),
        sa.Column('plan_data', JSONB, server_default='{}'),
        sa.Column('pdf_file_url', sa.Text(), nullable=True),
        sa.Column('student_level', sa.String(20), nullable=True),
        sa.Column('student_count', sa.Integer(), nullable=True),
        sa.Column('weak_students_count', sa.Integer(), nullable=True),
        sa.Column('excellent_students_count', sa.Integer(), nullable=True),
        sa.Column('focus_area', sa.String(30), nullable=True),
        sa.Column('examples_count', sa.Integer(), server_default='5'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )


def downgrade():
    op.drop_table('lesson_plans')
    op.drop_table('lesson_pages')
    op.drop_table('textbooks')
