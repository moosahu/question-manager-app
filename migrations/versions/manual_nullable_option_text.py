"""Make Option.text nullable

Revision ID: manual_nullable_option_text
Revises: 
Create Date: 2025-05-02 00:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'manual_nullable_option_text' # Use a descriptive manual ID
down_revision = None # Assuming this is the first migration for the project
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('option', schema=None) as batch_op:
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=True) # Change nullable to True
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('option', schema=None) as batch_op:
        # IMPORTANT: Reverting nullable=True to nullable=False might fail
        # if there are existing rows with NULL in the 'text' column.
        # Consider adding logic here to handle NULLs before changing the constraint,
        # e.g., setting them to an empty string.
        # For simplicity now, we just revert the nullable status.
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=False) # Change nullable back to False
    # ### end Alembic commands ###

