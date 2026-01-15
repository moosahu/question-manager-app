# src/models/gamification.py
"""
نماذج نظام التحفيز (Gamification)
محدّث: يناير 2026
"""
from datetime import datetime, date
from src.extensions import db


# ==================== 1. جدول الإنجازات Achievements ====================

class Achievement(db.Model):
    """الإنجازات التي يمكن للطالب فتحها"""
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)  # مثل: first_quiz, perfect_10
    achievement_type = db.Column(db.String(50), nullable=False)  # quiz, streak, score, special
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    rarity = db.Column(db.String(20), nullable=False, default='common')  # common, rare, epic, legendary
    
    # شروط الفتح
    conditions = db.Column(db.JSON, nullable=True, default={})
    # مثال: {"type": "quiz_count", "value": 10}
    # مثال: {"type": "perfect_score", "count": 3}
    # مثال: {"type": "streak_days", "days": 7}
    
    # الترتيب والتفعيل
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    student_achievements = db.relationship(
        'StudentAchievement', 
        backref='achievement', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'code': self.code,
            'type': self.achievement_type,
            'title': self.title,
            'description': self.description,
            'icon': self.icon,
            'points': self.points,
            'rarity': self.rarity,
            'conditions': self.conditions
        }


# ==================== 2. جدول نقاط الطالب StudentPoints ====================

class StudentPoints(db.Model):
    """نقاط الطالب الإجمالية"""
    __tablename__ = 'student_points'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False, unique=True)
    
    # النقاط
    total_points = db.Column(db.Integer, nullable=False, default=0)  # النقاط الحالية
    lifetime_points = db.Column(db.Integer, nullable=False, default=0)  # إجمالي النقاط المكتسبة
    
    # المستوى (محسوب من total_points)
    level = db.Column(db.Integer, nullable=False, default=1)
    
    # السلسلة
    current_streak = db.Column(db.Integer, nullable=False, default=0)
    longest_streak = db.Column(db.Integer, nullable=False, default=0)
    last_activity_date = db.Column(db.Date, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes للأداء
    __table_args__ = (
        db.Index('idx_total_points', 'total_points'),
        db.Index('idx_level', 'level'),
        db.Index('idx_student_id', 'student_id'),
    )

    @classmethod
    def get_or_create(cls, student_id: int):
        """إرجاع سجل النقاط للطالب أو إنشاؤه إذا لم يكن موجوداً"""
        obj = cls.query.filter_by(student_id=student_id).first()
        if not obj:
            obj = cls(
                student_id=student_id,
                total_points=0,
                lifetime_points=0,
                level=1,
                current_streak=0,
                longest_streak=0
            )
            db.session.add(obj)
            db.session.commit()
        return obj

    def add_points(
        self,
        amount: int,
        reason: str = None,
        reference_type: str = None,
        reference_id: int = None,
    ):
        """إضافة نقاط للطالب مع إنشاء حركة في point_transactions"""
        self.total_points += amount
        self.lifetime_points += amount
        
        # تحديث المستوى
        self.update_level()

        # إنشاء transaction
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

    def update_level(self):
        """تحديث المستوى بناءً على النقاط"""
        if self.total_points >= 1000:
            self.level = 5
        elif self.total_points >= 500:
            self.level = 4
        elif self.total_points >= 250:
            self.level = 3
        elif self.total_points >= 100:
            self.level = 2
        else:
            self.level = 1

    def update_streak(self, activity_date: date = None):
        """تحديث السلسلة"""
        if activity_date is None:
            activity_date = date.today()
        
        if self.last_activity_date is None:
            # أول نشاط
            self.current_streak = 1
            self.longest_streak = 1
        elif self.last_activity_date == activity_date:
            # نفس اليوم - لا تغيير
            pass
        elif (activity_date - self.last_activity_date).days == 1:
            # اليوم التالي - استمرار السلسلة
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        else:
            # انقطاع - إعادة السلسلة
            self.current_streak = 1
        
        self.last_activity_date = activity_date

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'student_id': self.student_id,
            'total_points': self.total_points,
            'lifetime_points': self.lifetime_points,
            'level': self.level,
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak,
            'last_activity_date': self.last_activity_date.isoformat() if self.last_activity_date else None
        }


# ==================== 3. جدول حركات النقاط PointTransaction ====================

class PointTransaction(db.Model):
    """سجل حركات النقاط"""
    __tablename__ = 'point_transactions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # يمكن أن يكون سالب (خصم نقاط)
    reason = db.Column(db.Text, nullable=True)
    
    # للربط مع المصدر (quiz, challenge, achievement, etc.)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Index للأداء
    __table_args__ = (
        db.Index('idx_student_created', 'student_id', 'created_at'),
    )

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'amount': self.amount,
            'reason': self.reason,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'created_at': self.created_at.isoformat()
        }


# ==================== 4. ربط الطالب بالإنجازات StudentAchievement ====================

class StudentAchievement(db.Model):
    """إنجازات الطالب المفتوحة"""
    __tablename__ = 'student_achievements'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    achievement_id = db.Column(
        db.Integer,
        db.ForeignKey('achievements.id', ondelete='CASCADE'),
        nullable=False,
    )
    
    # التقدم (للإنجازات التدريجية)
    progress = db.Column(db.Integer, nullable=False, default=0)
    is_unlocked = db.Column(db.Boolean, nullable=False, default=False)
    
    unlocked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'student_id',
            'achievement_id',
            name='uq_student_achievement',
        ),
        db.Index('idx_student_unlocked', 'student_id', 'is_unlocked'),
    )

    @classmethod
    def unlock(cls, student_id: int, achievement_code: str):
        """فتح إنجاز لطالب معيّن إن لم يكن مفتوحاً من قبل"""
        ach = Achievement.query.filter_by(
            code=achievement_code,
            is_active=True,
        ).first()
        if not ach:
            return None

        existing = cls.query.filter_by(
            student_id=student_id,
            achievement_id=ach.id,
        ).first()
        
        if existing:
            if not existing.is_unlocked:
                existing.is_unlocked = True
                existing.unlocked_at = datetime.utcnow()
                db.session.commit()
                return existing
            return None  # Already unlocked

        obj = cls(
            student_id=student_id, 
            achievement_id=ach.id,
            is_unlocked=True,
            unlocked_at=datetime.utcnow()
        )
        db.session.add(obj)
        db.session.commit()
        return obj

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'achievement': self.achievement.to_dict() if self.achievement else None,
            'progress': self.progress,
            'is_unlocked': self.is_unlocked,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None
        }


# ==================== 5. جدول التحديات Challenge ====================

class Challenge(db.Model):
    """التحديات (يومية، أسبوعية، شهرية، خاصة)"""
    __tablename__ = 'challenges'

    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات التحدي
    code = db.Column(db.String(50), nullable=False, unique=True)  # daily_quiz_3, weekly_streak_7
    challenge_type = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, special
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(100), nullable=False, default='🎯')
    
    # الهدف والمكافأة
    target_type = db.Column(db.String(50), nullable=False)  # quiz_count, perfect_score, points, streak
    target_value = db.Column(db.Integer, nullable=False)  # العدد المطلوب
    points = db.Column(db.Integer, nullable=False, default=50)
    
    # الفترة الزمنية
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    
    # الحالة
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=True)  # يتكرر تلقائياً؟
    
    # إضافات
    difficulty = db.Column(db.String(20), nullable=False, default='medium')  # easy, medium, hard
    category = db.Column(db.String(50), nullable=True)  # للتصنيف
    
    # التواريخ
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    student_challenges = db.relationship(
        'StudentChallenge',
        backref='challenge',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # Indexes
    __table_args__ = (
        db.Index('idx_type_active', 'challenge_type', 'is_active'),
        db.Index('idx_dates', 'start_date', 'end_date'),
    )

    def to_dict(self, include_progress=False):
        """تحويل إلى dictionary"""
        data = {
            'id': self.id,
            'code': self.code,
            'type': self.challenge_type,
            'title': self.title,
            'description': self.description,
            'icon': self.icon,
            'target_type': self.target_type,
            'target_value': self.target_value,
            'points': self.points,
            'difficulty': self.difficulty,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
        }
        return data

    def is_valid_for_date(self, check_date: date = None):
        """هل التحدي صالح في تاريخ معين؟"""
        if check_date is None:
            check_date = date.today()
        
        if not self.is_active:
            return False
        
        if self.start_date and check_date < self.start_date:
            return False
        
        if self.end_date and check_date > self.end_date:
            return False
        
        return True


# ==================== 6. جدول تقدم الطالب في التحديات StudentChallenge ====================

class StudentChallenge(db.Model):
    """تتبع تقدم الطالب في التحديات"""
    __tablename__ = 'student_challenges'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='CASCADE'),
        nullable=False,
    )
    
    # التقدم
    progress = db.Column(db.Integer, nullable=False, default=0)
    target = db.Column(db.Integer, nullable=False)  # نسخة من target_value
    
    # الحالة
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # التواريخ
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        db.Index('idx_student_challenge', 'student_id', 'challenge_id'),
        db.Index('idx_student_completed', 'student_id', 'is_completed'),
    )

    @classmethod
    def get_or_create(cls, student_id: int, challenge_id: int):
        """الحصول على تقدم الطالب أو إنشاء سجل جديد"""
        obj = cls.query.filter_by(
            student_id=student_id,
            challenge_id=challenge_id
        ).first()
        
        if not obj:
            challenge = Challenge.query.get(challenge_id)
            if not challenge:
                return None
            
            obj = cls(
                student_id=student_id,
                challenge_id=challenge_id,
                progress=0,
                target=challenge.target_value,
                is_completed=False
            )
            db.session.add(obj)
            db.session.commit()
        
        return obj

    def update_progress(self, increment: int = 1):
        """تحديث التقدم"""
        self.progress = min(self.progress + increment, self.target)
        
        # التحقق من الإكمال
        if self.progress >= self.target and not self.is_completed:
            self.is_completed = True
            self.completed_at = datetime.utcnow()
            return True  # تم الإكمال الآن
        
        db.session.commit()
        return False

    def get_percentage(self):
        """النسبة المئوية للإكمال"""
        if self.target == 0:
            return 0
        return int((self.progress / self.target) * 100)

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'challenge': self.challenge.to_dict() if self.challenge else None,
            'progress': self.progress,
            'target': self.target,
            'percentage': self.get_percentage(),
            'is_completed': self.is_completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'started_at': self.started_at.isoformat()
        }


# ==================== Backward Compatibility ====================
# للحفاظ على التوافق مع الكود القديم

DailyChallenge = Challenge  # Alias
ChallengeCompletion = StudentChallenge  # Alias
