# src/routes/gamification_routes.py
"""
API Routes لنظام التحفيز (Gamification)
"""

from flask import Blueprint, request, jsonify
from functools import wraps

from src.services.gamification_service import gamification_service
from src.models.student import Student

# إنشاء Blueprint
gamification_bp = Blueprint('gamification', __name__, url_prefix='/api/gamification')


# ============================================
# Decorators
# ============================================

def student_required(f):
    """Decorator للتحقق من أن المستخدم طالب"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: التحقق من JWT token أو session
        # للتبسيط، نفترض أن الطالب مسجل دخول
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# Points Routes
# ============================================

@gamification_bp.route('/points/<int:student_id>', methods=['GET'])
@student_required
def get_points(student_id):
    """
    الحصول على نقاط الطالب
    
    GET /api/gamification/points/1
    """
    try:
        points_data = gamification_service.get_student_points(student_id)
        
        return jsonify({
            'success': True,
            'data': points_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """
    لوحة المتصدرين
    
    GET /api/gamification/leaderboard?limit=10
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        leaderboard = gamification_service.get_points_leaderboard(limit)
        
        return jsonify({
            'success': True,
            'data': leaderboard
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Achievements Routes
# ============================================

@gamification_bp.route('/achievements/<int:student_id>', methods=['GET'])
@student_required
def get_achievements(student_id):
    """
    الحصول على إنجازات الطالب
    
    GET /api/gamification/achievements/1
    """
    try:
        achievements = gamification_service.get_student_achievements(student_id)
        
        return jsonify({
            'success': True,
            'data': achievements
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Challenges Routes
# ============================================

@gamification_bp.route('/challenge/today', methods=['GET'])
def get_today_challenge():
    """
    الحصول على تحدي اليوم
    
    GET /api/gamification/challenge/today
    """
    try:
        challenge = gamification_service.get_today_challenge()
        
        if challenge:
            return jsonify({
                'success': True,
                'data': challenge
            })
        else:
            return jsonify({
                'success': False,
                'message': 'لا يوجد تحدي اليوم'
            }), 404
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/challenge/progress/<int:student_id>', methods=['GET'])
@student_required
def get_challenge_progress(student_id):
    """
    الحصول على تقدم الطالب في تحدي اليوم
    
    GET /api/gamification/challenge/progress/1
    """
    try:
        progress = gamification_service.get_student_challenge_progress(student_id)
        
        return jsonify({
            'success': True,
            'data': progress
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Stats Routes
# ============================================

@gamification_bp.route('/stats/<int:student_id>', methods=['GET'])
@student_required
def get_student_stats(student_id):
    """
    إحصائيات شاملة للطالب
    
    GET /api/gamification/stats/1
    """
    try:
        # النقاط
        points_data = gamification_service.get_student_points(student_id)
        
        # الإنجازات
        achievements = gamification_service.get_student_achievements(student_id)
        
        # تقدم التحدي
        challenge_progress = gamification_service.get_student_challenge_progress(student_id)
        
        # السلسلة
        streak = gamification_service._calculate_streak(student_id)
        
        return jsonify({
            'success': True,
            'data': {
                'points': points_data,
                'achievements': {
                    'total_unlocked': achievements['total_unlocked'],
                    'total_achievements': achievements['total_achievements'],
                    'percentage': round(
                        (achievements['total_unlocked'] / achievements['total_achievements'] * 100) 
                        if achievements['total_achievements'] > 0 else 0,
                        1
                    )
                },
                'challenge': challenge_progress,
                'streak_days': streak
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
