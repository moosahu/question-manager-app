# src/services/question_classifier.py
"""
خدمة تصنيف الأسئلة بالذكاء الاصطناعي (Gemini)
"""

import os
import json
import time
import re
import logging
from typing import Dict, List, Optional
from flask import current_app

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from src.extensions import db
    from src.models.question import Question
except ImportError:
    try:
        from extensions import db
        from models.question import Question
    except ImportError:
        db = None
        Question = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuestionClassifier:
    """خدمة تصنيف الأسئلة بالذكاء الاصطناعي"""
    
    def __init__(self):
        self.model = None
        self.is_configured = False
        self.api_key = None
        # ✅ موديل مستقر - gemini-2.0-flash
        self.model_name = 'gemini-2.0-flash'
        self.last_request_time = 0
        self.min_delay = 7.0  # 7 ثواني (حوالي 8-9 طلبات/دقيقة)
    
    def _ensure_configured(self) -> bool:
        """تهيئة Gemini"""
        if self.is_configured and self.model:
            return True
        
        try:
            self.api_key = (
                current_app.config.get('GOOGLE_AI_API_KEY') or 
                os.getenv('GOOGLE_AI_API_KEY') or
                os.getenv('GEMINI_API_KEY')
            )
            
            if not self.api_key:
                logger.error("❌ GOOGLE_AI_API_KEY غير موجود")
                return False
            
            if not GEMINI_AVAILABLE:
                logger.error("❌ google-generativeai غير مثبت")
                return False
            
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.is_configured = True
            logger.info(f"✅ تم تهيئة Gemini: {self.model_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Gemini: {e}")
            return False
    
    def _wait_for_rate_limit(self):
        """انتظار لتجنب rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()
    
    def _call_api_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """استدعاء API مع retry"""
        
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                response = self.model.generate_content(prompt)
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                if '429' in error_str or 'quota' in error_str.lower():
                    wait_time = 65
                    match = re.search(r'seconds:\s*(\d+)', error_str)
                    if match:
                        wait_time = int(match.group(1)) + 5
                    
                    logger.warning(f"⏳ Rate limit - انتظار {wait_time}s (محاولة {attempt+1})")
                    time.sleep(wait_time)
                    continue
                
                logger.error(f"❌ خطأ: {error_str[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                return None
        
        return None
    
    def classify_question(self, question_text: str, options: List[str] = None) -> Dict:
        """تصنيف سؤال واحد"""
        if not self._ensure_configured():
            return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'AI not configured'}
        
        try:
            prompt = self._build_prompt(question_text, options)
            response_text = self._call_api_with_retry(prompt)
            
            if not response_text:
                return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'API failed'}
            
            return self._parse_response(response_text)
            
        except Exception as e:
            return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': str(e)}
    
    def _build_prompt(self, question_text: str, options: List[str] = None) -> str:
        """بناء prompt التصنيف"""
        options_text = ""
        if options:
            options_text = "\nالخيارات: " + " | ".join([opt for opt in options if opt])
        
        return f"""صنّف سؤال الكيمياء:

السؤال: {question_text}{options_text}

أجب بـ JSON فقط:
{{"difficulty": "easy/medium/hard", "bloom_level": "remember/understand/apply/analyze/evaluate/create"}}

الصعوبة:
- easy: تعريف، حقيقة بسيطة
- medium: تطبيق قانون، حساب بسيط
- hard: حسابات معقدة، ربط مفاهيم

بلوم:
- remember: اذكر، عرّف
- understand: اشرح، فسّر
- apply: احسب، طبّق
- analyze: قارن، حلل
- evaluate: قيّم
- create: صمم"""
    
    def _parse_response(self, response_text: str) -> Dict:
        """تحليل رد AI"""
        result = {'difficulty': 'medium', 'bloom_level': 'remember'}
        
        try:
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group())
                
                if parsed.get('difficulty') in ['easy', 'medium', 'hard']:
                    result['difficulty'] = parsed['difficulty']
                if parsed.get('bloom_level') in ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']:
                    result['bloom_level'] = parsed['bloom_level']
        except:
            pass
        
        return result
    
    def classify_all_unclassified(self, batch_size: int = 10, delay: float = 7.0) -> Dict:
        """تصنيف الأسئلة غير المصنفة"""
        if not self._ensure_configured():
            return {'success': False, 'error': 'AI not configured'}
        
        if Question is None:
            return {'success': False, 'error': 'Question model not available'}
        
        self.min_delay = max(delay, 6.0)
        
        try:
            questions = Question.query.filter(
                (Question.difficulty == 'medium') | (Question.difficulty == None),
                (Question.bloom_level == 'remember') | (Question.bloom_level == None)
            ).limit(batch_size).all()
            
            if not questions:
                return {'success': True, 'message': 'لا توجد أسئلة تحتاج تصنيف', 'classified': 0, 'total': 0}
            
            stats = {
                'total': len(questions),
                'classified': 0,
                'failed': 0,
                'difficulty_counts': {'easy': 0, 'medium': 0, 'hard': 0},
                'bloom_counts': {}
            }
            
            logger.info(f"🔄 بدء تصنيف {len(questions)} سؤال (تأخير {self.min_delay}s)...")
            
            for i, question in enumerate(questions):
                try:
                    q_text = question.question_text or "[سؤال بالصورة]"
                    options = [opt.option_text for opt in question.options if opt.option_text]
                    
                    classification = self.classify_question(q_text, options)
                    
                    if 'error' not in classification:
                        question.difficulty = classification['difficulty']
                        question.bloom_level = classification['bloom_level']
                        
                        stats['classified'] += 1
                        stats['difficulty_counts'][classification['difficulty']] += 1
                        stats['bloom_counts'][classification['bloom_level']] = \
                            stats['bloom_counts'].get(classification['bloom_level'], 0) + 1
                        
                        logger.info(f"  ✅ [{i+1}/{len(questions)}] Q{question.question_id}: {classification['difficulty']}, {classification['bloom_level']}")
                    else:
                        stats['failed'] += 1
                        logger.warning(f"  ⚠️ [{i+1}/{len(questions)}] Q{question.question_id}: فشل")
                    
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"  ❌ [{i+1}/{len(questions)}] Q{question.question_id}: {e}")
            
            db.session.commit()
            
            stats['success'] = True
            stats['message'] = f"تم تصنيف {stats['classified']} من {stats['total']} سؤال"
            
            logger.info(f"✅ {stats['message']}")
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_classification_stats(self) -> Dict:
        """إحصائيات التصنيف"""
        if Question is None:
            return {'error': 'Question model not available'}
        
        try:
            total = Question.query.count()
            
            difficulty_stats = db.session.query(
                Question.difficulty, db.func.count(Question.question_id)
            ).group_by(Question.difficulty).all()
            
            bloom_stats = db.session.query(
                Question.bloom_level, db.func.count(Question.question_id)
            ).group_by(Question.bloom_level).all()
            
            return {
                'total_questions': total,
                'by_difficulty': {d or 'unset': c for d, c in difficulty_stats},
                'by_bloom_level': {b or 'unset': c for b, c in bloom_stats}
            }
        except Exception as e:
            return {'error': str(e)}


question_classifier = QuestionClassifier()
