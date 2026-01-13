# src/models/gamification.py
from datetime import datetime
from src.extensions import db


# ==================== 1. جدول الإنجازات Achievements ====================

class Achievement(db.Model):
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    achievement_type = db.Column(db.String, nullable=False, unique=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String, nullable=False)
    points = db.Column(db.Integer, nullable=True, default=0)
    conditions = db.Column(db.JSON, nullable=True, default={})
    is_active = db.Column(db.Boolean, nullable=True, default=True)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    student_achievements = db.relationship(
        'StudentAchievement', backref='achievement', lazy=True
    )


# ==================== 2. جدول نقاط الطالب StudentPoints ====================

class StudentPoints(db.Model):
    __tablename__ = 'student_points'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False, unique=True)
    total_points = db.Column(db.Integer, nullable=False, default=0)
    lifetime_points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=True,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @classmethod
    def get_or_create(cls, student_id: int):
        """إرجاع سجل النقاط للطالب أو إنشاؤه إذا لم يكن موجوداً."""
        obj = cls.query.filter_by(student_id=student_id).first()
        if not obj:
            obj = cls(
                student_id=student_id,
                total_points=0,
                lifetime_points=0,
            )
            db.session.add(obj)
            db.session.commit()
        return obj

    def add_points(
        self,
        amount: int,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
    ):
        """إضافة نقاط للطالب مع إنشاء حركة في point_transactions."""
        self.total_points += amount
        self.lifetime_points += amount

        tx = PointTransaction(
            student_id=self.student_id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db.session.add(tx)
        db.session.commit()
        return tx


# ==================== 3. جدول حركات النقاط PointTransaction ====================

class PointTransaction(db.Model):
    __tablename__ = 'point_transactions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    reference_type = db.Column(db.String, nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    # ملاحظة: لا يوجد ForeignKey للـ student_points حسب السكيمة الحالية، لذلك لا نعرّف relationship عكسي هنا.


# ==================== 4. ربط الطالب بالإنجازات StudentAchievement ====================

class StudentAchievement(db.Model):
    __tablename__ = 'student_achievements'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    achievement_id = db.Column(
        db.Integer,
        db.ForeignKey('achievements.id'),
        nullable=False,
    )
    unlocked_at = db.Column(
        db.DateTime,
        nullable=True,
        default=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'student_id',
            'achievement_id',
            name='uq_student_achievement',
        ),
    )

    @classmethod
    def unlock(cls, student_id: int, achievement_type: str):
        """فتح إنجاز لطالب معيّن إن لم يكن مفتوحاً من قبل."""
        ach = Achievement.query.filter_by(
            achievement_type=achievement_type,
            is_active=True,
        ).first()
        if not ach:
            return None

        existing = cls.query.filter_by(
            student_id=student_id,
            achievement_id=ach.id,
        ).first()
        if existing:
            return None

        obj = cls(student_id=student_id, achievement_id=ach.id)
        db.session.add(obj)
        db.session.commit()
        return obj


# ==================== 5. جدول التحديات اليومية DailyChallenge ====================

class DailyChallenge(db.Model):
    __tablename__ = 'daily_challenges'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    challenge_type = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String, nullable=True, default='🎯')
    points = db.Column(db.Integer, nullable=True, default=25)
    conditions = db.Column(db.JSON, nullable=True, default={})
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    completions = db.relationship(
        'ChallengeCompletion',
        backref='challenge',
        lazy=True,
    )


# ==================== 6. جدول إكمال التحديات ChallengeCompletion ====================

class ChallengeCompletion(db.Model):
    __tablename__ = 'challenge_completions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('daily_challenges.id'),
        nullable=False,
    )
    completed_at = db.Column(
        db.DateTime,
        nullable=True,
        default=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'student_id',
            'challenge_id',
            name='uq_challenge_completion',
        ),
    )
