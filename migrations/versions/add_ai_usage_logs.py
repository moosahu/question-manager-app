"""add ai_usage_logs table

Revision ID: add_ai_usage_logs
Revises: manual_nullable_option_text
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_ai_usage_logs'
down_revision = 'manual_nullable_option_text'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_usage_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=True),
        sa.Column('ai_provider', sa.String(30), nullable=True),
        sa.Column('operation_type', sa.String(30), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), default=0),
        sa.Column('output_tokens', sa.Integer(), default=0),
        sa.Column('cost_usd', sa.Float(), default=0.0),
        sa.Column('duration_seconds', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_ai_usage_logs_created_at', 'ai_usage_logs', ['created_at'])
    op.create_index('ix_ai_usage_logs_teacher_id', 'ai_usage_logs', ['teacher_id'])


def downgrade():
    op.drop_index('ix_ai_usage_logs_teacher_id')
    op.drop_index('ix_ai_usage_logs_created_at')
    op.drop_table('ai_usage_logs')
