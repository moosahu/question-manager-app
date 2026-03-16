"""add teacher_student link and class_code

Revision ID: add_teacher_student_link
Revises:
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_teacher_student_link'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    import secrets
    import string

    def gen_code(used):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(6))
            if code not in used:
                used.add(code)
                return code

    conn = op.get_bind()
    used_codes = set()

    # 1. class_code للمعلمين
    with op.batch_alter_table('teachers') as batch_op:
        batch_op.add_column(
            sa.Column('class_code', sa.String(10), unique=True, nullable=True)
        )
    for (tid,) in conn.execute(sa.text('SELECT id FROM teachers')).fetchall():
        conn.execute(
            sa.text('UPDATE teachers SET class_code = :c WHERE id = :id'),
            {'c': gen_code(used_codes), 'id': tid}
        )

    # 2. class_code للأدمن (جدول user)
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(
            sa.Column('class_code', sa.String(10), unique=True, nullable=True)
        )
    for (uid,) in conn.execute(sa.text('SELECT id FROM "user" WHERE is_admin = true')).fetchall():
        conn.execute(
            sa.text('UPDATE "user" SET class_code = :c WHERE id = :id'),
            {'c': gen_code(used_codes), 'id': uid}
        )

    # 3. جدول الربط (teacher أو admin)
    op.create_table(
        'teacher_students',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('teacher_id', sa.Integer(),
                  sa.ForeignKey('teachers.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('admin_id', sa.Integer(),
                  sa.ForeignKey('user.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('student_id', sa.Integer(),
                  sa.ForeignKey('students.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint('student_id', name='uq_teacher_students_student'),
    )
    op.create_index('ix_teacher_students_teacher_id', 'teacher_students', ['teacher_id'])
    op.create_index('ix_teacher_students_admin_id',   'teacher_students', ['admin_id'])
    op.create_index('ix_teacher_students_student_id', 'teacher_students', ['student_id'])


def downgrade():
    op.drop_table('teacher_students')
    with op.batch_alter_table('teachers') as batch_op:
        batch_op.drop_column('class_code')
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('class_code')
