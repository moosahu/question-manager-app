"""add unique index on question_text + lesson_id

Revision ID: add_question_uniqueness
Revises: add_r2_video_url
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_question_uniqueness'
down_revision = 'add_r2_video_url'
branch_labels = None
depends_on = None


def upgrade():
    # حذف المكررات أولاً — نبقي فقط أصغر question_id لكل (question_text, lesson_id)
    op.execute("""
        DELETE FROM questions
        WHERE question_id NOT IN (
            SELECT MIN(question_id)
            FROM questions
            WHERE question_text IS NOT NULL
            GROUP BY question_text, lesson_id
        )
        AND question_text IS NOT NULL
    """)

    # إضافة unique index (يشمل نصوص فقط، يتجاهل أسئلة الصور)
    op.create_index(
        'uq_question_text_lesson',
        'questions',
        ['question_text', 'lesson_id'],
        unique=True,
        postgresql_where=sa.text('question_text IS NOT NULL'),
    )


def downgrade():
    op.drop_index('uq_question_text_lesson', table_name='questions')
