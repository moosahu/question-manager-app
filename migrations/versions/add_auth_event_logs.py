"""add auth_event_logs table

Revision ID: add_auth_event_logs
Revises: add_error_tracking
Create Date: 2026-03-14

جدول واحد:
  auth_event_logs — عدّادات أحداث المصادقة (401 جلسة منتهية, 403 رفض صلاحية)
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_auth_event_logs'
down_revision = 'add_error_tracking'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auth_event_logs',
        sa.Column('id',         sa.Integer,    primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(30), nullable=False),   # session_expired | permission_denied
        sa.Column('user_type',  sa.String(20), nullable=True),    # admin | teacher | student | unknown
        sa.Column('created_at', sa.DateTime,   nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_auth_event_logs_event_type', 'auth_event_logs', ['event_type'])
    op.create_index('ix_auth_event_logs_created_at', 'auth_event_logs', ['created_at'])


def downgrade():
    op.drop_index('ix_auth_event_logs_created_at', table_name='auth_event_logs')
    op.drop_index('ix_auth_event_logs_event_type', table_name='auth_event_logs')
    op.drop_table('auth_event_logs')
