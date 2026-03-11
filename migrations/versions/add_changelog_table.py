"""add changelog table

Revision ID: add_changelog_table
Revises:
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_changelog_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS changelogs (
            id           SERIAL PRIMARY KEY,
            version      VARCHAR(20) NOT NULL,
            entries      TEXT NOT NULL,
            published_at TIMESTAMP DEFAULT NOW(),
            is_active    BOOLEAN DEFAULT TRUE
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS changelogs")
