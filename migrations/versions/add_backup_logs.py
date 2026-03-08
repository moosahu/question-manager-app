"""Add backup_logs table

Revision ID: add_backup_logs
Revises: add_backup_settings_tracking
Create Date: 2026-03-09
"""
from alembic import op


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS backup_logs (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES "user"(id),
            status          VARCHAR(10) NOT NULL,
            destination     VARCHAR(20),
            file_size       INTEGER,
            error_msg       TEXT,
            questions_count INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_logs_user_id   ON backup_logs (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_logs_created_at ON backup_logs (created_at);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS backup_logs;")
