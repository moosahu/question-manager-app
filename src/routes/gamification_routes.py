# src/routes/gamification_routes.py
"""
API Routes لنظام التحفيز (Gamification)
محدّث: يناير 2026
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
    
    Response:
    {
        "success": true,
        "data": {
            "student_id": 1,
            "total_points": 450,
            "lifetime_points": 500,
            "level": 4,
            "rank": 3,
            "current_streak": 7,
            "longest_streak": 15,
            "points_to_next_level": 50,
            "next_level_threshold": 500
        }
    }
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


@gamification_bp.route('/points/<int:student_id>/add', methods=['POST'])
@student_required
def add_points(student_id):
    """
    إضافة نقاط للطالب (Admin only)
    
    POST /api/gamification/points/1/add
    Body: {
        "amount": 50,
        "reason": "مكافأة خاصة"
    }
    """
    try:
        data = request.get_json()
        amount = data.get('amount', 0)
        reason = data.get('reason', 'مكافأة')
        
        if amount <= 0:
            return jsonify({
                'success': False,
                'error': 'المبلغ يجب أن يكون أكبر من صفر'
            }), 400
        
        result = gamification_service.add_points(
            student_id,
            amount,
            reason
        )
        
        return jsonify({
            'success': True,
            'data': result
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
    
    GET /api/gamification/leaderboard?limit=10&offset=0
    
    Response:
    {
        "success": true,
        "data": [
            {
                "rank": 1,
                "student_id": 7,
                "name": "Hussain",
                "username": "moosahu11",
                "total_points": 1250,
                "level": 5,
                "current_streak": 15
            },
            ...
        ]
    }
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        leaderboard = gamification_service.get_points_leaderboard(limit, offset)
        
        return jsonify({
            'success': True,
            'data': leaderboard,
            'total': len(leaderboard)
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
    
    Response:
    {
        "success": true,
        "data": {
            "achievements": [
                {
                    "achievement": {...},
                    "is_unlocked": true,
                    "unlocked_at": "2026-01-15T10:30:00",
                    "progress": 10
                },
                ...
            ],
            "total_achievements": 20,
            "total_unlocked": 5,
            "completion_rate": 25.0
        }
    }
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


@gamification_bp.route('/achievements/<int:student_id>/check', methods=['POST'])
@student_required
def check_achievements(student_id):
    """
    فحص وفتح الإنجازات المؤهل لها الطالب
    
    POST /api/gamification/achievements/1/check
    
    Response:
    {
        "success": true,
        "unlocked": [
            {
                "achievement": {...},
                "points_earned": 50
            }
        ],
        "total_unlocked": 2
    }
    """
    try:
        unlocked = gamification_service.check_and_unlock_achievements(student_id)
        
        return jsonify({
            'success': True,
            'unlocked': unlocked,
            'total_unlocked': len(unlocked)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Challenges Routes
# ============================================

@gamification_bp.route('/challenges', methods=['GET'])
def get_challenges():
    """
    الحصول على التحديات النشطة
    
    GET /api/gamification/challenges?type=daily&student_id=1
    
    Query Params:
    - type: daily, weekly, monthly, special (optional)
    - student_id: لإضافة معلومات التقدم (optional)
    
    Response:
    {
        "success": true,
        "data": [
            {
                "id": 1,
                "type": "daily",
                "title": "حل 3 اختبارات",
                "target_value": 3,
                "points": 50,
                "progress": 2,
                "percentage": 66,
                "is_completed": false
            },
            ...
        ]
    }
    """
    try:
        challenge_type = request.args.get('type')
        student_id = request.args.get('student_id', type=int)
        
        challenges = gamification_service.get_active_challenges(
            challenge_type=challenge_type,
            student_id=student_id
        )
        
        return jsonify({
            'success': True,
            'data': challenges,
            'total': len(challenges)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/challenges/today', methods=['GET'])
def get_today_challenge():
    """
    الحصول على تحدي اليوم
    
    GET /api/gamification/challenges/today
    
    Response:
    {
        "success": true,
        "data": {
            "id": 1,
            "title": "حل 3 اختبارات اليوم",
            "description": "اختبر نفسك في 3 اختبارات مختلفة",
            "target_value": 3,
            "points": 50
        }
    }
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


@gamification_bp.route('/challenges/<int:student_id>/progress', methods=['GET'])
@student_required
def get_challenge_progress(student_id):
    """
    الحصول على تقدم الطالب في التحديات
    
    GET /api/gamification/challenges/1/progress
    GET /api/gamification/challenges/1/progress?challenge_id=5
    
    Response:
    {
        "success": true,
        "data": {
            "challenges": [...],
            "total": 5,
            "completed": 2
        }
    }
    """
    try:
        challenge_id = request.args.get('challenge_id', type=int)
        
        progress = gamification_service.get_student_challenge_progress(
            student_id,
            challenge_id
        )
        
        return jsonify({
            'success': True,
            'data': progress
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/challenges/<int:student_id>/update', methods=['POST'])
@student_required
def update_challenge_progress(student_id):
    """
    تحديث تقدم الطالب في التحدي
    
    POST /api/gamification/challenges/1/update
    Body: {
        "challenge_id": 5,
        "increment": 1
    }
    
    Response:
    {
        "success": true,
        "just_completed": true,
        "progress": {...},
        "points_earned": 50
    }
    """
    try:
        data = request.get_json()
        challenge_id = data.get('challenge_id')
        increment = data.get('increment', 1)
        
        if not challenge_id:
            return jsonify({
                'success': False,
                'error': 'challenge_id مطلوب'
            }), 400
        
        result = gamification_service.update_challenge_progress(
            student_id,
            challenge_id,
            increment
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Streak Routes
# ============================================

@gamification_bp.route('/streak/<int:student_id>', methods=['GET'])
@student_required
def get_streak(student_id):
    """
    الحصول على سلسلة الطالب
    
    GET /api/gamification/streak/1
    
    Response:
    {
        "success": true,
        "data": {
            "current_streak": 7,
            "longest_streak": 15,
            "last_activity_date": "2026-01-15"
        }
    }
    """
    try:
        points_data = gamification_service.get_student_points(student_id)
        
        return jsonify({
            'success': True,
            'data': {
                'current_streak': points_data['current_streak'],
                'longest_streak': points_data['longest_streak']
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/streak/<int:student_id>/update', methods=['POST'])
@student_required
def update_streak(student_id):
    """
    تحديث سلسلة الطالب
    
    POST /api/gamification/streak/1/update
    
    Response:
    {
        "success": true,
        "data": {
            "current_streak": 8,
            "longest_streak": 15,
            "streak_increased": true
        }
    }
    """
    try:
        result = gamification_service.update_streak(student_id)
        
        return jsonify({
            'success': True,
            'data': result
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
    
    Response:
    {
        "success": true,
        "data": {
            "points": {...},
            "achievements": {...},
            "challenges": {...},
            "streak": {...}
        }
    }
    """
    try:
        # النقاط
        points_data = gamification_service.get_student_points(student_id)
        
        # الإنجازات
        achievements = gamification_service.get_student_achievements(student_id)
        
        # التحديات
        challenges = gamification_service.get_student_challenge_progress(student_id)
        
        return jsonify({
            'success': True,
            'data': {
                'points': points_data,
                'achievements': {
                    'total_unlocked': achievements['total_unlocked'],
                    'total_achievements': achievements['total_achievements'],
                    'completion_rate': achievements['completion_rate']
                },
                'challenges': challenges,
                'streak': {
                    'current': points_data['current_streak'],
                    'longest': points_data['longest_streak']
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gamification_bp.route('/stats/system', methods=['GET'])
def get_system_stats():
    """
    إحصائيات النظام الكاملة (Admin only)
    
    GET /api/gamification/stats/system
    
    Response:
    {
        "success": true,
        "data": {
            "total_points_distributed": 125000,
            "total_achievements_unlocked": 450,
            "total_challenges_completed": 320,
            "active_students": 67
        }
    }
    """
    try:
        stats = gamification_service.get_system_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Backward Compatibility Routes
# ============================================

@gamification_bp.route('/challenge/today', methods=['GET'])
def get_today_challenge_legacy():
    """Backward compatibility للـ route القديم"""
    return get_today_challenge()


@gamification_bp.route('/challenge/progress/<int:student_id>', methods=['GET'])
@student_required
def get_challenge_progress_legacy(student_id):
    """Backward compatibility للـ route القديم"""
    return get_challenge_progress(student_id)
