# src/services/question_classifier.py
"""
خدمة تصنيف الأسئلة بالذكاء الاصطناعي (Gemini)
مع معالجة Rate Limit (10 طلبات/دقيقة)
"""

import os
import json
import time
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
from flask import current_app

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai غير مثبت!")

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
    """خدمة تصنيف الأسئلة بالذكاء الاصطناعي مع معالجة Rate Limit"""
    
    def __init__(self):
        self.model = None
        self.is_configured = False
        self.api_key = None
        self.model_name = 'gemini-2.0-flash-exp'
        self.last_request_time = 0
        self.min_delay = 7.0  # 7 ثواني بين كل طلب (10 طلبات/دقيقة + هامش أمان)
    
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
        """انتظار ذكي لتجنب rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            time.sleep(wait_time)
        self.last_request_time = time.time()
    
    def _call_api_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """استدعاء API مع إعادة المحاولة عند rate limit"""
        
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                response = self.model.generate_content(prompt)
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                # Rate limit (429)
                if '429' in error_str or 'quota' in error_str.lower():
                    # استخراج وقت الانتظار
                    wait_time = 65  # افتراضي دقيقة + 5 ثواني
                    match = re.search(r'seconds:\s*(\d+)', error_str)
                    if match:
                        wait_time = int(match.group(1)) + 5
                    
                    logger.warning(f"⏳ Rate limit - انتظار {wait_time}s (محاولة {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    self.last_request_time = time.time()
                    continue
                
                # أخطاء أخرى
                logger.error(f"❌ خطأ API: {error_str[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
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
            logger.error(f"❌ خطأ: {e}")
            return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': str(e)}
    
    def _build_prompt(self, question_text: str, options: List[str] = None) -> str:
        """بناء prompt التصنيف"""
        options_text = ""
        if options:
            options_text = "\nالخيارات: " + " | ".join([opt for opt in options if opt])
        
        return f"""صنّف سؤال الكيمياء التالي:

السؤال: {question_text}{options_text}

أجب بـ JSON فقط:
{{"difficulty": "easy/medium/hard", "bloom_level": "remember/understand/apply/analyze/evaluate/create"}}

معايير الصعوبة:
- easy: تعريف مباشر، حقيقة بسيطة
- medium: تطبيق قانون، حساب بسيط، فهم مفهوم
- hard: حسابات معقدة، ربط عدة مفاهيم، تحليل عميق

معايير بلوم:
- remember: اذكر، عرّف، سمّ
- understand: اشرح، وضّح، فسّر
- apply: احسب، طبّق، أوجد
- analyze: قارن، حلل، ميّز
- evaluate: قيّم، احكم
- create: صمم، اقترح"""
    
    def _parse_response(self, response_text: str) -> Dict:
        """تحليل رد AI"""
        result = {'difficulty': 'medium', 'bloom_level': 'remember'}
        
        try:
            # استخراج JSON
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group())
                
                valid_diff = ['easy', 'medium', 'hard']
                valid_bloom = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']
                
                if parsed.get('difficulty') in valid_diff:
                    result['difficulty'] = parsed['difficulty']
                if parsed.get('bloom_level') in valid_bloom:
                    result['bloom_level'] = parsed['bloom_level']
        except:
            pass
        
        return result
    
    def classify_all_unclassified(self, batch_size: int = 10, delay: float = 7.0) -> Dict:
        """
        تصنيف الأسئلة غير المصنفة
        
        ⚠️ Rate Limit: 10 طلبات/دقيقة
        - batch_size=10 موصى به
        - delay=7 ثواني بين كل طلب
        """
        if not self._ensure_configured():
            return {'success': False, 'error': 'AI not configured'}
        
        if Question is None:
            return {'success': False, 'error': 'Question model not available'}
        
        # تحديث التأخير
        self.min_delay = max(delay, 6.0)
        
        try:
            # جلب الأسئلة غير المصنفة
            questions = Question.query.filter(
                (Question.difficulty == 'medium') | (Question.difficulty == None),
                (Question.bloom_level == 'remember') | (Question.bloom_level == None)
            ).limit(batch_size).all()
            
            if not questions:
                return {
                    'success': True,
                    'message': 'لا توجد أسئلة تحتاج تصنيف',
                    'classified': 0,
                    'total': 0
                }
            
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
                        logger.warning(f"  ⚠️ [{i+1}/{len(questions)}] Q{question.question_id}: {classification.get('error', 'unknown')[:50]}")
                    
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"  ❌ [{i+1}/{len(questions)}] Q{question.question_id}: {e}")
            
            # حفظ التغييرات
            db.session.commit()
            
            stats['success'] = True
            stats['message'] = f"تم تصنيف {stats['classified']} من {stats['total']} سؤال"
            
            logger.info(f"✅ {stats['message']}")
            logger.info(f"   الصعوبة: {stats['difficulty_counts']}")
            logger.info(f"   بلوم: {stats['bloom_counts']}")
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ خطأ: {e}")
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


# Instance
question_classifier = QuestionClassifier()
