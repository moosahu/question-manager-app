"""Add last_backup_time and backup_count to backup_settings

Revision ID: add_backup_settings_tracking
Revises:
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.execute("""
        ALTER TABLE backup_settings
        ADD COLUMN IF NOT EXISTS last_backup_time TIMESTAMP,
        ADD COLUMN IF NOT EXISTS backup_count INTEGER DEFAULT 0 NOT NULL;
    """)

def downgrade():
    op.execute("""
        ALTER TABLE backup_settings
        DROP COLUMN IF EXISTS last_backup_time,
        DROP COLUMN IF EXISTS backup_count;
    """)
