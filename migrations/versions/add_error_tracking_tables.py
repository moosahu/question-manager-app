"""add error tracking tables

Revision ID: add_error_tracking
Revises:
Create Date: 2026-03-14

جدولان:
  error_reports  — سجل كل خطأ مُرسَل من التطبيق
  error_groups   — تجميع الأخطاء المتشابهة تحت مجموعة واحدة
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_error_tracking'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── جدول المجموعات (يُنشأ أولاً لأن error_reports يرجع إليه) ──
    op.create_table(
        'error_groups',
        sa.Column('group_hash',    sa.String(32),  primary_key=True),
        sa.Column('error_summary', sa.String(200),  nullable=False),
        sa.Column('source',        sa.String(20),   nullable=False),   # auto_crash | api_error | screen_error | user_report
        sa.Column('priority',      sa.String(10),   nullable=False),   # CRITICAL | HIGH | MEDIUM | LOW
        sa.Column('count',         sa.Integer,      nullable=False, server_default='1'),
        sa.Column('first_seen',    sa.DateTime,     nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen',     sa.DateTime,     nullable=False, server_default=sa.func.now()),
        sa.Column('is_resolved',   sa.Boolean,      nullable=False, server_default='false'),
        sa.Column('resolved_at',   sa.DateTime,     nullable=True),
    )

    # ── جدول السجلات الفردية ──
    op.create_table(
        'error_reports',
        sa.Column('id',            sa.Integer,      primary_key=True, autoincrement=True),
        sa.Column('group_hash',    sa.String(32),   sa.ForeignKey('error_groups.group_hash'), nullable=True),
        sa.Column('source',        sa.String(20),   nullable=False),
        sa.Column('priority',      sa.String(10),   nullable=False),
        sa.Column('error_message', sa.Text,         nullable=False),
        sa.Column('stack_trace',   sa.Text,         nullable=True),
        sa.Column('screen_name',   sa.String(100),  nullable=True),
        sa.Column('error_context', sa.String(200),  nullable=True),
        sa.Column('user_type',     sa.String(20),   nullable=True),    # admin | teacher | student | unknown
        sa.Column('app_version',   sa.String(20),   nullable=True),
        sa.Column('created_at',    sa.DateTime,     nullable=False, server_default=sa.func.now()),
    )

    # ── فهارس لتسريع الاستعلامات ──
    op.create_index('ix_error_reports_group_hash',  'error_reports', ['group_hash'])
    op.create_index('ix_error_reports_source',      'error_reports', ['source'])
    op.create_index('ix_error_reports_created_at',  'error_reports', ['created_at'])
    op.create_index('ix_error_groups_is_resolved',  'error_groups',  ['is_resolved'])
    op.create_index('ix_error_groups_priority',     'error_groups',  ['priority'])


def downgrade():
    op.drop_table('error_reports')
    op.drop_table('error_groups')
