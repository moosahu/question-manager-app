# src/services/gamification_service.py
"""
خدمات نظام التحفيز (Gamification Service)
محدّث: يناير 2026
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from sqlalchemy import desc, and_, or_

from src.extensions import db
from src.models.gamification import (
    Achievement,
    StudentAchievement,
    Challenge,
    StudentChallenge,
    StudentPoints,
    PointTransaction
)
from src.models.student import Student
from src.models.student_result import StudentResult


class GamificationService:
    """خدمة نظام التحفيز"""

    # ==================== Points Management ====================

    def get_student_points(self, student_id: int) -> Dict:
        """الحصول على نقاط الطالب"""
        points = StudentPoints.get_or_create(student_id)
        
        # حساب الترتيب
        rank = self._calculate_rank(student_id)
        
        # حساب النقاط للمستوى التالي
        next_level = points.level + 1
        current_threshold = self._get_level_threshold(points.level)
        next_threshold = self._get_level_threshold(next_level)
        points_to_next = next_threshold - points.total_points if next_level <= 5 else 0
        
        return {
            'student_id': student_id,
            'total_points': points.total_points,
            'lifetime_points': points.lifetime_points,
            'level': points.level,
            'rank': rank,
            'current_streak': points.current_streak,
            'longest_streak': points.longest_streak,
            'points_to_next_level': max(0, points_to_next),
            'next_level_threshold': next_threshold if next_level <= 5 else None
        }

    def add_points(
        self,
        student_id: int,
        amount: int,
        reason: str = None,
        reference_type: str = None,
        reference_id: int = None
    ) -> Dict:
        """إضافة نقاط للطالب"""
        points = StudentPoints.get_or_create(student_id)
        old_level = points.level
        
        # إضافة النقاط
        points.add_points(amount, reason, reference_type, reference_id)
        
        new_level = points.level
        leveled_up = new_level > old_level
        
        return {
            'success': True,
            'new_total': points.total_points,
            'amount_added': amount,
            'leveled_up': leveled_up,
            'old_level': old_level,
            'new_level': new_level
        }

    def get_points_leaderboard(self, limit: int = 10, offset: int = 0) -> List[Dict]:
        """لوحة المتصدرين"""
        top_students = StudentPoints.query.order_by(
            desc(StudentPoints.total_points)
        ).limit(limit).offset(offset).all()
        
        leaderboard = []
        for idx, points in enumerate(top_students, start=offset + 1):
            student = Student.query.get(points.student_id)
            if student:
                leaderboard.append({
                    'rank': idx,
                    'student_id': points.student_id,
                    'name': student.name,
                    'username': student.username,
                    'total_points': points.total_points,
                    'level': points.level,
                    'current_streak': points.current_streak
                })
        
        return leaderboard

    def _get_level_threshold(self, level: int) -> int:
        """الحد الأدنى من النقاط للمستوى"""
        thresholds = {
            1: 0,
            2: 100,
            3: 250,
            4: 500,
            5: 1000
        }
        return thresholds.get(level, 1000)

    def _calculate_rank(self, student_id: int) -> int:
        """حساب ترتيب الطالب"""
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        if not student_points:
            return 0
        
        rank = StudentPoints.query.filter(
            StudentPoints.total_points > student_points.total_points
        ).count() + 1
        
        return rank

    # ==================== Achievements Management ====================

    def get_student_achievements(self, student_id: int) -> Dict:
        """الحصول على إنجازات الطالب"""
        # كل الإنجازات المتاحة
        all_achievements = Achievement.query.filter_by(is_active=True).all()
        
        # الإنجازات المفتوحة
        unlocked = StudentAchievement.query.filter_by(
            student_id=student_id,
            is_unlocked=True
        ).all()
        
        unlocked_dict = {sa.achievement_id: sa for sa in unlocked}
        
        achievements_list = []
        for ach in all_achievements:
            student_ach = unlocked_dict.get(ach.id)
            achievements_list.append({
                'achievement': ach.to_dict(),
                'is_unlocked': student_ach is not None,
                'unlocked_at': student_ach.unlocked_at.isoformat() if student_ach else None,
                'progress': student_ach.progress if student_ach else 0
            })
        
        return {
            'achievements': achievements_list,
            'total_achievements': len(all_achievements),
            'total_unlocked': len(unlocked),
            'completion_rate': round((len(unlocked) / len(all_achievements) * 100) if all_achievements else 0, 1)
        }

    def unlock_achievement(self, student_id: int, achievement_code: str) -> Optional[Dict]:
        """فتح إنجاز للطالب"""
        student_ach = StudentAchievement.unlock(student_id, achievement_code)
        
        if student_ach:
            # إضافة نقاط الإنجاز
            achievement = student_ach.achievement
            if achievement.points > 0:
                self.add_points(
                    student_id,
                    achievement.points,
                    f"إنجاز: {achievement.title}",
                    'achievement',
                    achievement.id
                )
            
            return {
                'success': True,
                'achievement': achievement.to_dict(),
                'points_earned': achievement.points
            }
        
        return None

    def check_and_unlock_achievements(self, student_id: int) -> List[Dict]:
        """فحص وفتح الإنجازات المؤهل لها الطالب"""
        unlocked = []
        
        # حساب الإحصائيات
        stats = self._calculate_student_stats(student_id)
        
        # فحص كل إنجاز
        all_achievements = Achievement.query.filter_by(is_active=True).all()
        for ach in all_achievements:
            if self._check_achievement_condition(ach, stats):
                result = self.unlock_achievement(student_id, ach.code)
                if result:
                    unlocked.append(result)
        
        return unlocked

    def _calculate_student_stats(self, student_id: int) -> Dict:
        """حساب إحصائيات الطالب للإنجازات"""
        # النقاط
        points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        # عدد الاختبارات
        total_quizzes = StudentResult.query.filter_by(student_id=student_id).count()
        
        # الدرجات الكاملة
        perfect_scores = StudentResult.query.filter_by(
            student_id=student_id
        ).filter(
            StudentResult.score == 100
        ).count()
        
        return {
            'total_quizzes': total_quizzes,
            'perfect_scores': perfect_scores,
            'total_points': points.total_points if points else 0,
            'current_streak': points.current_streak if points else 0,
            'level': points.level if points else 1
        }

    def _check_achievement_condition(self, achievement: Achievement, stats: Dict) -> bool:
        """التحقق من شرط الإنجاز"""
        conditions = achievement.conditions or {}
        condition_type = conditions.get('type')
        
        if condition_type == 'quiz_count':
            return stats['total_quizzes'] >= conditions.get('value', 0)
        elif condition_type == 'perfect_score':
            return stats['perfect_scores'] >= conditions.get('count', 0)
        elif condition_type == 'points':
            return stats['total_points'] >= conditions.get('value', 0)
        elif condition_type == 'streak_days':
            return stats['current_streak'] >= conditions.get('days', 0)
        elif condition_type == 'level':
            return stats['level'] >= conditions.get('level', 0)
        
        return False

    # ==================== Challenges Management ====================

    def get_active_challenges(
        self,
        challenge_type: str = None,
        student_id: int = None
    ) -> List[Dict]:
        """الحصول على التحديات النشطة"""
        today = date.today()
        
        query = Challenge.query.filter(
            Challenge.is_active == True,
            or_(
                Challenge.start_date == None,
                Challenge.start_date <= today
            ),
            or_(
                Challenge.end_date == None,
                Challenge.end_date >= today
            )
        )
        
        if challenge_type:
            query = query.filter(Challenge.challenge_type == challenge_type)
        
        challenges = query.all()
        
        result = []
        for challenge in challenges:
            challenge_dict = challenge.to_dict()
            
            # إذا طُلب معلومات طالب معين
            if student_id:
                progress = StudentChallenge.query.filter_by(
                    student_id=student_id,
                    challenge_id=challenge.id
                ).first()
                
                if progress:
                    challenge_dict['progress'] = progress.progress
                    challenge_dict['is_completed'] = progress.is_completed
                    challenge_dict['percentage'] = progress.get_percentage()
                else:
                    challenge_dict['progress'] = 0
                    challenge_dict['is_completed'] = False
                    challenge_dict['percentage'] = 0
            
            result.append(challenge_dict)
        
        return result

    def get_today_challenge(self) -> Optional[Dict]:
        """الحصول على تحدي اليوم"""
        challenges = self.get_active_challenges(challenge_type='daily')
        return challenges[0] if challenges else None

    def get_student_challenge_progress(
        self,
        student_id: int,
        challenge_id: int = None
    ) -> Dict:
        """الحصول على تقدم الطالب في التحديات"""
        if challenge_id:
            # تحدي محدد
            progress = StudentChallenge.query.filter_by(
                student_id=student_id,
                challenge_id=challenge_id
            ).first()
            
            if progress:
                return progress.to_dict()
            else:
                challenge = Challenge.query.get(challenge_id)
                if challenge:
                    return {
                        'challenge': challenge.to_dict(),
                        'progress': 0,
                        'target': challenge.target_value,
                        'percentage': 0,
                        'is_completed': False
                    }
        else:
            # كل التحديات
            progresses = StudentChallenge.query.filter_by(
                student_id=student_id
            ).all()
            
            return {
                'challenges': [p.to_dict() for p in progresses],
                'total': len(progresses),
                'completed': sum(1 for p in progresses if p.is_completed)
            }
        
        return {}

    def update_challenge_progress(
        self,
        student_id: int,
        challenge_id: int,
        increment: int = 1
    ) -> Dict:
        """تحديث تقدم الطالب في التحدي"""
        progress = StudentChallenge.get_or_create(student_id, challenge_id)
        
        if not progress:
            return {'success': False, 'error': 'التحدي غير موجود'}
        
        if progress.is_completed:
            return {
                'success': False,
                'message': 'التحدي مكتمل بالفعل',
                'progress': progress.to_dict()
            }
        
        just_completed = progress.update_progress(increment)
        
        # إذا تم الإكمال الآن، أضف النقاط
        if just_completed:
            challenge = progress.challenge
            self.add_points(
                student_id,
                challenge.points,
                f"تحدي: {challenge.title}",
                'challenge',
                challenge.id
            )
        
        return {
            'success': True,
            'just_completed': just_completed,
            'progress': progress.to_dict(),
            'points_earned': progress.challenge.points if just_completed else 0
        }

    def auto_update_challenges(self, student_id: int, action_type: str, value: int = 1):
        """تحديث تلقائي للتحديات بناءً على نشاط الطالب"""
        active_challenges = self.get_active_challenges(student_id=student_id)
        
        updated = []
        for challenge in active_challenges:
            # التحقق من نوع التحدي
            if challenge['target_type'] == action_type:
                result = self.update_challenge_progress(
                    student_id,
                    challenge['id'],
                    value
                )
                if result.get('success'):
                    updated.append(result)
        
        return updated

    # ==================== Streak Management ====================

    def update_streak(self, student_id: int) -> Dict:
        """تحديث سلسلة الطالب"""
        points = StudentPoints.get_or_create(student_id)
        old_streak = points.current_streak
        
        points.update_streak()
        db.session.commit()
        
        return {
            'current_streak': points.current_streak,
            'longest_streak': points.longest_streak,
            'streak_increased': points.current_streak > old_streak
        }

    def _calculate_streak(self, student_id: int) -> int:
        """حساب السلسلة الحالية"""
        points = StudentPoints.query.filter_by(student_id=student_id).first()
        return points.current_streak if points else 0

    # ==================== Statistics ====================

    def get_system_stats(self) -> Dict:
        """إحصائيات النظام الكاملة"""
        total_points_distributed = db.session.query(
            db.func.sum(StudentPoints.lifetime_points)
        ).scalar() or 0
        
        total_achievements_unlocked = StudentAchievement.query.filter_by(
            is_unlocked=True
        ).count()
        
        total_challenges_completed = StudentChallenge.query.filter_by(
            is_completed=True
        ).count()
        
        active_students = StudentPoints.query.filter(
            StudentPoints.total_points > 0
        ).count()
        
        return {
            'total_points_distributed': total_points_distributed,
            'total_achievements_unlocked': total_achievements_unlocked,
            'total_challenges_completed': total_challenges_completed,
            'active_students': active_students
        }


# ==================== Singleton Instance ====================
gamification_service = GamificationService()
