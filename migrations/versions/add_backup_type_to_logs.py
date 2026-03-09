"""Add backup_type column to backup_logs

Revision ID: add_backup_type_to_logs
Revises: add_backup_logs
Create Date: 2026-03-09
"""
from alembic import op


def upgrade():
    op.execute("""
        ALTER TABLE backup_logs
        ADD COLUMN IF NOT EXISTS backup_type VARCHAR(20) DEFAULT 'automatic';
    """)
    op.execute("""
        ALTER TABLE backup_logs
        ADD COLUMN IF NOT EXISTS sections_included TEXT;
    """)


def downgrade():
    op.execute("ALTER TABLE backup_logs DROP COLUMN IF EXISTS backup_type;")
    op.execute("ALTER TABLE backup_logs DROP COLUMN IF EXISTS sections_included;")
