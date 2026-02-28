"""add teacher_feature_overrides table

Revision ID: add_teacher_feature_overrides
Revises:
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_teacher_feature_overrides'
down_revision = None  # عدّله لآخر migration عندك
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'teacher_feature_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('feature_key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=50), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', 'feature_key', name='uq_teacher_feature'),
    )
    op.create_index('ix_teacher_feature_overrides_teacher_id', 'teacher_feature_overrides', ['teacher_id'])


def downgrade():
    op.drop_index('ix_teacher_feature_overrides_teacher_id', table_name='teacher_feature_overrides')
    op.drop_table('teacher_feature_overrides')
