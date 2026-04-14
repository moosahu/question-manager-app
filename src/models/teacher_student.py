"""
نموذج ربط الطالب بمعلم أو بالأدمن
طالب واحد → سجل واحد فقط (UNIQUE على student_id)
  - إما teacher_id مضبوط (مرتبط بمعلم)
  - أو admin_id مضبوط (مرتبط بالأدمن)
"""
from src.extensions import db
from datetime import datetime


class TeacherStudent(db.Model):
    """جدول ربط الطالب بمعلمه أو بالأدمن"""
    __tablename__ = 'teacher_students'

    id = db.Column(db.Integer, primary_key=True)

    # معلم أو أدمن — أحدهما مضبوط والآخر null
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey('teachers.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )

    # UNIQUE على student_id → طالب واحد في قائمة واحدة فقط
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    section   = db.Column(db.String(50),  nullable=True)  # الشعبة (أ، ب، ج ...)
    aruco_id  = db.Column(db.Integer,     nullable=True)  # ArUco marker ID ثابت (0–249)

    # العلاقات
    teacher = db.relationship('Teacher', backref=db.backref('linked_students', lazy='dynamic'))
    student = db.relationship('Student', backref=db.backref('teacher_link', uselist=False))

    @property
    def owner_type(self):
        """نوع المالك: teacher أو admin"""
        return 'teacher' if self.teacher_id else 'admin'

    @staticmethod
    def next_aruco_id(teacher_id, admin_id):
        """يرجع أصغر aruco_id غير مستخدم (0–249) لهذا المعلم/الأدمن."""
        from sqlalchemy import func
        q = TeacherStudent.query.filter(
            (TeacherStudent.teacher_id == teacher_id) if teacher_id
            else (TeacherStudent.admin_id == admin_id)
        ).filter(TeacherStudent.aruco_id.isnot(None))
        used = {r.aruco_id for r in q.all()}
        for i in range(250):
            if i not in used:
                return i
        return None  # امتلأ (250 طالب)

    def __repr__(self):
        return f'<TeacherStudent {self.owner_type} student={self.student_id}>'
