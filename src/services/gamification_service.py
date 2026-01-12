# src/services/gamification_service.py
"""
خدمة التحفيز (Gamification)
تدير النقاط والإنجازات والتحديات
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
import random

from src.models.gamification import (
    StudentPoints, PointTransaction, Achievement, 
    StudentAchievement, DailyChallenge, ChallengeCompletion
)
from src.models.student import Student
from src.models.student_result import StudentResult
from src.extensions import db


class GamificationService:
    """خدمة التحفيز"""
    
    def __init__(self):
        """تهيئة الخدمة"""
        pass
    
    # ============================================
    # نظام النقاط
    # ============================================
    
    def award_points_for_quiz(self, student_id: int, quiz_result: StudentResult) -> Dict:
        """منح نقاط للطالب بعد حل اختبار"""
        try:
            points_data = StudentPoints.get_or_create(student_id)
            
            # حساب النقاط بناءً على الدرجة
            base_points = 10  # نقاط أساسية
            
            score = quiz_result.score_percentage
            if score >= 90:
                bonus = 10  # ممتاز
            elif score >= 80:
                bonus = 7   # جيد جداً
            elif score >= 70:
                bonus = 5   # جيد
            elif score >= 60:
                bonus = 3   # مقبول
            else:
                bonus = 0   # ضعيف
            
            total_points = base_points + bonus
            
            # إضافة النقاط
            transaction = points_data.add_points(
                amount=total_points,
                reason=f"إكمال اختبار: {quiz_result.quiz_name} ({score}%)",
                reference_type='quiz',
                reference_id=quiz_result.id
            )
            
            # التحقق من الإنجازات
            achievements_unlocked = self._check_achievements_after_quiz(
                student_id, quiz_result
            )
            
            return {
                'success': True,
                'points_awarded': total_points,
                'total_points': points_data.total_points,
                'achievements_unlocked': achievements_unlocked
            }
            
        except Exception as e:
            print(f"❌ خطأ في award_points_for_quiz: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_student_points(self, student_id: int) -> Dict:
        """الحصول على نقاط الطالب"""
        points_data = StudentPoints.get_or_create(student_id)
        
        return {
            'total_points': points_data.total_points,
            'lifetime_points': points_data.lifetime_points,
            'rank': self._get_student_rank(student_id)
        }
    
    def get_points_leaderboard(self, limit: int = 10) -> List[Dict]:
        """لوحة المتصدرين"""
        top_students = StudentPoints.query.order_by(
            StudentPoints.total_points.desc()
        ).limit(limit).all()
        
        leaderboard = []
        for idx, sp in enumerate(top_students, 1):
            student = Student.query.get(sp.student_id)
            if student:
                leaderboard.append({
                    'rank': idx,
                    'student_id': student.id,
                    'student_name': student.name,
                    'points': sp.total_points,
                    'grade': student.grade
                })
        
        return leaderboard
    
    def _get_student_rank(self, student_id: int) -> int:
        """ترتيب الطالب"""
        student_points = StudentPoints.get_or_create(student_id)
        
        rank = StudentPoints.query.filter(
            StudentPoints.total_points > student_points.total_points
        ).count() + 1
        
        return rank
    
    # ============================================
    # نظام الإنجازات
    # ============================================
    
    def _check_achievements_after_quiz(self, student_id: int, 
                                      quiz_result: StudentResult) -> List[Dict]:
        """التحقق من الإنجازات بعد حل اختبار"""
        unlocked = []
        
        # 1. إنجاز "أول اختبار"
        quiz_count = StudentResult.query.filter_by(student_id=student_id).count()
        if quiz_count == 1:
            ach = self._unlock_achievement(student_id, 'first_quiz')
            if ach:
                unlocked.append(ach)
        
        # 2. إنجاز "100%"
        if quiz_result.score_percentage == 100:
            ach = self._unlock_achievement(student_id, 'perfect_score')
            if ach:
                unlocked.append(ach)
        
        # 3. إنجاز "5 اختبارات في يوم"
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        today_quizzes = StudentResult.query.filter(
            StudentResult.student_id == student_id,
            StudentResult.created_at >= today_start
        ).count()
        
        if today_quizzes >= 5:
            ach = self._unlock_achievement(student_id, 'solve_5_day')
            if ach:
                unlocked.append(ach)
        
        # 4. إنجاز "سلسلة متصلة"
        streak = self._calculate_streak(student_id)
        if streak >= 7:
            ach = self._unlock_achievement(student_id, 'streak_7')
            if ach:
                unlocked.append(ach)
        elif streak >= 3:
            ach = self._unlock_achievement(student_id, 'streak_3')
            if ach:
                unlocked.append(ach)
        
        # 5. إنجاز "تحسن 20%"
        improvement = self._calculate_improvement(student_id)
        if improvement >= 20:
            ach = self._unlock_achievement(student_id, 'improvement_20')
            if ach:
                unlocked.append(ach)
        
        return unlocked
    
    def _unlock_achievement(self, student_id: int, achievement_type: str) -> Optional[Dict]:
        """فتح إنجاز"""
        try:
            student_ach = StudentAchievement.unlock(student_id, achievement_type)
            
            if student_ach:
                achievement = student_ach.achievement
                return {
                    'achievement_type': achievement.achievement_type,
                    'title': achievement.title,
                    'description': achievement.description,
                    'icon': achievement.icon,
                    'points': achievement.points
                }
            
            return None
            
        except Exception as e:
            print(f"❌ خطأ في _unlock_achievement: {e}")
            return None
    
    def get_student_achievements(self, student_id: int) -> Dict:
        """الحصول على إنجازات الطالب"""
        # الإنجازات المفتوحة
        unlocked = StudentAchievement.query.filter_by(student_id=student_id).all()
        unlocked_types = [sa.achievement.achievement_type for sa in unlocked]
        
        unlocked_list = [{
            'achievement_type': sa.achievement.achievement_type,
            'title': sa.achievement.title,
            'description': sa.achievement.description,
            'icon': sa.achievement.icon,
            'points': sa.achievement.points,
            'unlocked_at': sa.unlocked_at.isoformat()
        } for sa in unlocked]
        
        # الإنجازات المغلقة
        all_achievements = Achievement.query.filter_by(is_active=True).all()
        locked_list = [{
            'achievement_type': ach.achievement_type,
            'title': ach.title,
            'description': ach.description,
            'icon': ach.icon,
            'points': ach.points,
            'locked': True
        } for ach in all_achievements if ach.achievement_type not in unlocked_types]
        
        return {
            'unlocked': unlocked_list,
            'locked': locked_list,
            'total_unlocked': len(unlocked_list),
            'total_achievements': len(all_achievements)
        }
    
    def _calculate_streak(self, student_id: int) -> int:
        """حساب السلسلة المتصلة (كم يوم متتالي)"""
        try:
            # جلب تواريخ الاختبارات
            results = StudentResult.query.filter_by(student_id=student_id)\
                .order_by(StudentResult.created_at.desc()).all()
            
            if not results:
                return 0
            
            # جمع الأيام الفريدة
            dates = set()
            for r in results:
                dates.add(r.created_at.date())
            
            dates = sorted(dates, reverse=True)
            
            # حساب السلسلة
            streak = 0
            expected_date = datetime.utcnow().date()
            
            for d in dates:
                if d == expected_date:
                    streak += 1
                    expected_date -= timedelta(days=1)
                elif d < expected_date:
                    break
            
            return streak
            
        except Exception as e:
            print(f"❌ خطأ في _calculate_streak: {e}")
            return 0
    
    def _calculate_improvement(self, student_id: int) -> float:
        """حساب نسبة التحسن"""
        try:
            results = StudentResult.query.filter_by(student_id=student_id)\
                .order_by(StudentResult.created_at.desc()).limit(10).all()
            
            if len(results) < 5:
                return 0
            
            recent_avg = sum(r.score_percentage for r in results[:5]) / 5
            older_avg = sum(r.score_percentage for r in results[5:]) / len(results[5:])
            
            if older_avg == 0:
                return 0
            
            improvement = ((recent_avg - older_avg) / older_avg) * 100
            return improvement
            
        except Exception as e:
            print(f"❌ خطأ في _calculate_improvement: {e}")
            return 0
    
    # ============================================
    # نظام التحديات اليومية
    # ============================================
    
    def generate_daily_challenge(self, challenge_date: date = None) -> Optional[DailyChallenge]:
        """توليد تحدي يومي"""
        if challenge_date is None:
            challenge_date = datetime.utcnow().date()
        
        # التحقق من وجود تحدي لهذا اليوم
        existing = DailyChallenge.query.filter_by(date=challenge_date).first()
        if existing:
            return existing
        
        # قائمة التحديات المتاحة
        challenges = [
            {
                'type': 'solve_5',
                'title': '🎯 خمسة في الشبكة',
                'description': 'حل 5 اختبارات اليوم',
                'icon': '🎯',
                'points': 25,
                'conditions': {'quiz_count': 5}
            },
            {
                'type': 'improve_score',
                'title': '📈 حسّن نفسك',
                'description': 'احصل على درجة أعلى من آخر اختبار',
                'icon': '📈',
                'points': 20,
                'conditions': {'improve': True}
            },
            {
                'type': 'perfect_quiz',
                'title': '💯 الدقة',
                'description': 'أجب على جميع أسئلة اختبار صحيحة',
                'icon': '💯',
                'points': 30,
                'conditions': {'perfect_score': True}
            },
            {
                'type': 'speed_quiz',
                'title': '⚡ السرعة',
                'description': 'أنهِ اختبار في أقل من 5 دقائق',
                'icon': '⚡',
                'points': 15,
                'conditions': {'time_limit': 300}
            },
            {
                'type': 'diverse',
                'title': '🎓 المتنوع',
                'description': 'حل اختبار من 3 مواضيع مختلفة',
                'icon': '🎓',
                'points': 20,
                'conditions': {'different_topics': 3}
            },
        ]
        
        # اختيار تحدي عشوائي
        challenge_data = random.choice(challenges)
        
        challenge = DailyChallenge(
            date=challenge_date,
            challenge_type=challenge_data['type'],
            title=challenge_data['title'],
            description=challenge_data['description'],
            icon=challenge_data['icon'],
            points=challenge_data['points'],
            conditions=challenge_data['conditions']
        )
        
        db.session.add(challenge)
        db.session.commit()
        
        return challenge
    
    def get_today_challenge(self) -> Optional[Dict]:
        """الحصول على تحدي اليوم"""
        today = datetime.utcnow().date()
        challenge = DailyChallenge.query.filter_by(date=today).first()
        
        if not challenge:
            challenge = self.generate_daily_challenge(today)
        
        if challenge:
            return {
                'id': challenge.id,
                'title': challenge.title,
                'description': challenge.description,
                'icon': challenge.icon,
                'points': challenge.points,
                'conditions': challenge.conditions
            }
        
        return None
    
    def check_challenge_completion(self, student_id: int, 
                                   quiz_result: StudentResult) -> Optional[Dict]:
        """التحقق من إكمال تحدي اليوم"""
        try:
            today = datetime.utcnow().date()
            challenge = DailyChallenge.query.filter_by(date=today).first()
            
            if not challenge:
                return None
            
            # التحقق من عدم إكماله مسبقاً
            existing = ChallengeCompletion.query.filter_by(
                student_id=student_id,
                challenge_id=challenge.id
            ).first()
            
            if existing:
                return None
            
            # التحقق من الشروط
            completed = False
            
            if challenge.challenge_type == 'solve_5':
                # عد اختبارات اليوم
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
                count = StudentResult.query.filter(
                    StudentResult.student_id == student_id,
                    StudentResult.created_at >= today_start
                ).count()
                completed = count >= 5
            
            elif challenge.challenge_type == 'perfect_quiz':
                completed = quiz_result.score_percentage == 100
            
            elif challenge.challenge_type == 'speed_quiz':
                completed = quiz_result.time_spent <= 300
            
            elif challenge.challenge_type == 'improve_score':
                # مقارنة مع آخر اختبار
                previous = StudentResult.query.filter(
                    StudentResult.student_id == student_id,
                    StudentResult.id < quiz_result.id
                ).order_by(StudentResult.created_at.desc()).first()
                
                if previous:
                    completed = quiz_result.score_percentage > previous.score_percentage
            
            elif challenge.challenge_type == 'diverse':
                # عد المواضيع المختلفة
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
                results = StudentResult.query.filter(
                    StudentResult.student_id == student_id,
                    StudentResult.created_at >= today_start
                ).all()
                
                topics = set(r.quiz_name for r in results)
                completed = len(topics) >= 3
            
            if completed:
                # تسجيل الإكمال
                completion = ChallengeCompletion(
                    student_id=student_id,
                    challenge_id=challenge.id
                )
                db.session.add(completion)
                
                # منح النقاط
                points_data = StudentPoints.get_or_create(student_id)
                points_data.add_points(
                    amount=challenge.points,
                    reason=f"إكمال تحدي: {challenge.title}",
                    reference_type='challenge',
                    reference_id=challenge.id
                )
                
                db.session.commit()
                
                return {
                    'challenge_completed': True,
                    'title': challenge.title,
                    'description': challenge.description,
                    'icon': challenge.icon,
                    'points_awarded': challenge.points
                }
            
            return None
            
        except Exception as e:
            print(f"❌ خطأ في check_challenge_completion: {e}")
            db.session.rollback()
            return None
    
    def get_student_challenge_progress(self, student_id: int) -> Dict:
        """تقدم الطالب في تحدي اليوم"""
        today = datetime.utcnow().date()
        challenge = DailyChallenge.query.filter_by(date=today).first()
        
        if not challenge:
            return {'no_challenge': True}
        
        # التحقق من الإكمال
        completed = ChallengeCompletion.query.filter_by(
            student_id=student_id,
            challenge_id=challenge.id
        ).first()
        
        if completed:
            return {
                'completed': True,
                'challenge': {
                    'title': challenge.title,
                    'description': challenge.description,
                    'icon': challenge.icon,
                    'points': challenge.points
                },
                'completed_at': completed.completed_at.isoformat()
            }
        
        # حساب التقدم
        progress = 0
        target = 0
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        
        if challenge.challenge_type == 'solve_5':
            count = StudentResult.query.filter(
                StudentResult.student_id == student_id,
                StudentResult.created_at >= today_start
            ).count()
            progress = count
            target = 5
        
        elif challenge.challenge_type == 'diverse':
            results = StudentResult.query.filter(
                StudentResult.student_id == student_id,
                StudentResult.created_at >= today_start
            ).all()
            topics = set(r.quiz_name for r in results)
            progress = len(topics)
            target = 3
        
        return {
            'completed': False,
            'challenge': {
                'title': challenge.title,
                'description': challenge.description,
                'icon': challenge.icon,
                'points': challenge.points
            },
            'progress': progress,
            'target': target
        }


# إنشاء instance واحد
gamification_service = GamificationService()
