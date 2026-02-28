"""
TeacherFeatureOverride - تحكم الأدمن بمميزات كل معلم
"""
from datetime import datetime
from src.extensions import db


# المميزات القابلة للتحكم مع قيمها الافتراضية
FEATURE_DEFAULTS = {
    'lesson_prep_enabled':             'true',
    'unit_distribution_enabled':       'true',
    'semester_distribution_enabled':   'true',
    'worksheet_enabled':               'true',
    'ai_analysis_enabled':             'true',
    'shared_library_enabled':          'true',
    'quota_single_lesson':             '5',
    'quota_unit_distribution':         '2',
    'quota_semester_distribution':     '2',
    'quota_worksheet':                 '3',
}

# أسماء عربية للعرض
FEATURE_LABELS = {
    'lesson_prep_enabled':             'تحضير الدروس',
    'unit_distribution_enabled':       'توزيع الوحدة',
    'semester_distribution_enabled':   'التوزيع الفصلي',
    'worksheet_enabled':               'أوراق العمل',
    'ai_analysis_enabled':             'تحليل الذكاء الاصطناعي',
    'shared_library_enabled':          'المكتبة المشتركة',
    'quota_single_lesson':             'حد تحضير الدرس اليومي',
    'quota_unit_distribution':         'حد توزيع الوحدة اليومي',
    'quota_semester_distribution':     'حد التوزيع الفصلي اليومي',
    'quota_worksheet':                 'حد أوراق العمل اليومي',
}


class TeacherFeatureOverride(db.Model):
    """تجاوز إعدادات ميزة معينة لمعلم محدد"""
    __tablename__ = 'teacher_feature_overrides'

    id          = db.Column(db.Integer, primary_key=True)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False)
    value       = db.Column(db.String(50), nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'feature_key', name='uq_teacher_feature'),
    )

    teacher = db.relationship('Teacher', backref=db.backref('feature_overrides', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<TeacherFeatureOverride T{self.teacher_id} {self.feature_key}={self.value}>'

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'feature_key': self.feature_key,
            'label': FEATURE_LABELS.get(self.feature_key, self.feature_key),
            'value': self.value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get_override(teacher_id, feature_key):
        """جلب override معين لمعلم"""
        return TeacherFeatureOverride.query.filter_by(
            teacher_id=teacher_id,
            feature_key=feature_key
        ).first()

    @staticmethod
    def set_override(teacher_id, feature_key, value):
        """تعيين أو تحديث override"""
        override = TeacherFeatureOverride.get_override(teacher_id, feature_key)
        if override:
            override.value = str(value)
            override.updated_at = datetime.utcnow()
        else:
            override = TeacherFeatureOverride(
                teacher_id=teacher_id,
                feature_key=feature_key,
                value=str(value)
            )
            db.session.add(override)
        db.session.commit()
        return override

    @staticmethod
    def delete_override(teacher_id, feature_key):
        """حذف override (يرجع للإعداد العام)"""
        override = TeacherFeatureOverride.get_override(teacher_id, feature_key)
        if override:
            db.session.delete(override)
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_all_overrides_for_teacher(teacher_id):
        """جلب كل overrides لمعلم معين"""
        return TeacherFeatureOverride.query.filter_by(teacher_id=teacher_id).all()
