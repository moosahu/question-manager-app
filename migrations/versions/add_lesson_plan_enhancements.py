"""Add course_id, original_pdf_url, is_taught, taught_at to lesson_plans + shared_plans + plan_ratings

Revision ID: add_lesson_plan_enhancements
Revises: add_textbooks_and_lesson_plans
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_lesson_plan_enhancements'
down_revision = 'add_textbooks_and_lesson_plans'
branch_labels = None
depends_on = None


def upgrade():
    # إضافة حقول جديدة لـ lesson_plans
    op.add_column('lesson_plans', sa.Column('course_id', sa.Integer(), sa.ForeignKey('course.id'), nullable=True))
    op.add_column('lesson_plans', sa.Column('original_pdf_url', sa.Text(), nullable=True))
    op.add_column('lesson_plans', sa.Column('is_taught', sa.Boolean(), server_default='false'))
    op.add_column('lesson_plans', sa.Column('taught_at', sa.DateTime(), nullable=True))

    # جدول المشاركات
    op.create_table('shared_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('lesson_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_by', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('visibility', sa.String(20), server_default='school'),
        sa.Column('avg_rating', sa.Float(), server_default='0'),
        sa.Column('use_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )

    # جدول التقييمات
    op.create_table('plan_ratings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('lesson_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('overall_rating', sa.Integer(), nullable=False),
        sa.Column('section_ratings', JSONB, server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('plan_id', 'teacher_id', name='unique_plan_teacher_rating'),
    )


def downgrade():
    op.drop_table('plan_ratings')
    op.drop_table('shared_plans')
    op.drop_column('lesson_plans', 'taught_at')
    op.drop_column('lesson_plans', 'is_taught')
    op.drop_column('lesson_plans', 'original_pdf_url')
    op.drop_column('lesson_plans', 'course_id')
