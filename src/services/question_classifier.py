# src/services/question_classifier.py
"""
خدمة تصنيف الأسئلة بالذكاء الاصطناعي (Gemini)
✅ محسّن: يكمل التصنيف حتى لو فشل سؤال
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
        self.model_name = 'gemini-2.0-flash'
        self.last_request_time = 0
        self.min_delay = 6.0
        self.consecutive_errors = 0  # عداد الأخطاء المتتالية
        self.max_consecutive_errors = 5  # الحد الأقصى للأخطاء المتتالية
    
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
    
    def _call_api_with_retry(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """استدعاء API مع retry محدود"""
        
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                response = self.model.generate_content(prompt)
                self.consecutive_errors = 0  # إعادة تعيين عداد الأخطاء
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                # Rate limit (429) - انتظر ثم أعد المحاولة
                if '429' in error_str or 'quota' in error_str.lower():
                    # بدل الانتظار الطويل، نرجع None ونكمل للسؤال التالي
                    # أو نوقف الدفعة الحالية ونحفظ التقدم
                    logger.warning(f"⏳ Rate limit - سيتم تخطي هذا السؤال")
                    self.consecutive_errors += 1
                    return None  # لا ننتظر، نرجع فوراً
                
                # أخطاء أخرى - سجل وارجع None
                logger.error(f"❌ خطأ API: {error_str[:80]}")
                self.consecutive_errors += 1
                return None
        
        return None
    
    def classify_question(self, question_text: str, options: List[str] = None) -> Dict:
        """تصنيف سؤال واحد"""
        default_result = {'difficulty': 'medium', 'bloom_level': 'remember'}
        
        if not self._ensure_configured():
            return {**default_result, 'error': 'AI not configured'}
        
        # تخطي الأسئلة الفارغة أو بالصورة فقط
        if not question_text or question_text == "[سؤال بالصورة]":
            return {**default_result, 'skipped': True}
        
        try:
            prompt = self._build_prompt(question_text, options)
            response_text = self._call_api_with_retry(prompt)
            
            if not response_text:
                return {**default_result, 'error': 'API failed'}
            
            return self._parse_response(response_text)
            
        except Exception as e:
            logger.error(f"❌ خطأ في classify_question: {str(e)[:50]}")
            return {**default_result, 'error': str(e)[:50]}
    
    def _build_prompt(self, question_text: str, options: List[str] = None) -> str:
        """بناء prompt التصنيف مع كلمات بلوم المفتاحية"""
        options_text = ""
        if options:
            filtered_options = [opt for opt in options if opt]
            if filtered_options:
                options_text = "\nالخيارات: " + " | ".join(filtered_options)
        
        return f"""صنّف سؤال الكيمياء التالي:

السؤال: {question_text}{options_text}

أجب بـ JSON فقط:
{{"difficulty": "easy/medium/hard", "bloom_level": "remember/understand/apply/analyze/evaluate/create"}}

=== معايير الصعوبة ===
- easy: تعريف مباشر، حقيقة بسيطة، تذكر معلومة
- medium: تطبيق قانون، حساب بسيط، فهم مفهوم، مقارنة
- hard: حسابات معقدة، ربط عدة مفاهيم، تحليل عميق، تقويم

=== مستويات بلوم (بالكلمات المفتاحية) ===

1. remember (المعرفة/التذكر):
   الكلمات: يعرّف، يحدد، يصف، يذكر، يسمّي، يعدّد، يحفظ، يكرر، يسترجع، يختار، يطابق، يتعرّف، يسرد، يضع قائمة
   مثال: "ما تعريف..." أو "اذكر..." أو "عدّد..." أو "سمّي..."

2. understand (الفهم):
   الكلمات: يلخّص، يفسّر، يشرح، يوضّح، يقارن، يصنّف، يستنتج، يترجم، يعيد صياغة، يستخرج، يتوقّع
   مثال: "اشرح..." أو "فسّر..." أو "ما الفرق بين..." أو "وضّح..."

3. apply (التطبيق):
   الكلمات: يحلّ، يحسب، يطبّق، يستخدم، يوجد، يرسم، يكمل، يبيّن، ينفّذ، يجرّب، يوظّف
   مثال: "احسب..." أو "طبّق..." أو "أوجد..." أو "استخدم القانون..."

4. analyze (التحليل):
   الكلمات: يحلّل، يقارن (بعمق)، يفكّك، يميّز، يربط، يستنبط، يفحص، يختبر، يصنّف (بمعايير)
   مثال: "حلّل..." أو "قارن بين... من حيث..." أو "ما العلاقة بين..."

5. evaluate (التقويم):
   الكلمات: يقيّم، يحكم، ينتقد، يبرر، يدافع، يقرر، يختار (مع تبرير)، يرتّب حسب الأهمية
   مثال: "قيّم..." أو "احكم على..." أو "أيهما أفضل ولماذا..."

6. create (الإبداع):
   الكلمات: يصمّم، يبتكر، يخترع، يؤلّف، يقترح، يخطط، يطوّر، ينشئ، يركّب (شيء جديد)
   مثال: "صمّم..." أو "اقترح طريقة..." أو "ابتكر..."

=== تعليمات مهمة ===
- إذا السؤال يبدأ بـ "ما/من/أي" للتعريف = remember
- إذا السؤال يطلب حساب أو تطبيق قانون = apply
- إذا السؤال يطلب مقارنة سطحية = understand
- إذا السؤال يطلب تحليل أو مقارنة عميقة = analyze
- أسئلة الاختيار من متعدد البسيطة غالباً = remember أو understand"""
    
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
        except Exception as e:
            logger.debug(f"تعذر تحليل الرد: {str(e)[:30]}")
        
        return result
    
    def classify_all_unclassified(self, batch_size: int = 20, delay: float = 8.0) -> Dict:
        """
        تصنيف الأسئلة غير المصنفة
        ✅ محسّن: يستخدم raw SQL للتحقق من ai_classified
        """
        if not self._ensure_configured():
            return {'success': False, 'error': 'AI not configured'}
        
        if Question is None:
            return {'success': False, 'error': 'Question model not available'}
        
        self.min_delay = max(delay, 8.0)
        self.consecutive_errors = 0
        
        try:
            # ✅ استخدام raw SQL للتحقق من ai_classified
            from sqlalchemy import text
            
            result = db.session.execute(
                text("SELECT question_id FROM questions WHERE ai_classified = FALSE LIMIT :limit"),
                {"limit": batch_size}
            )
            question_ids = [row[0] for row in result.fetchall()]
            
            if not question_ids:
                logger.info("🎉 لا توجد أسئلة تحتاج تصنيف!")
                return {
                    'success': True,
                    'message': '🎉 تم تصنيف جميع الأسئلة!',
                    'classified': 0,
                    'total': 0
                }
            
            # جلب الأسئلة بناءً على IDs
            questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
            logger.info(f"📋 وجدت {len(questions)} سؤال غير مصنف")
            
            if not questions:
                return {
                    'success': True, 
                    'message': '🎉 تم تصنيف جميع الأسئلة!', 
                    'classified': 0, 
                    'total': 0
                }
            
            stats = {
                'total': len(questions),
                'classified': 0,
                'failed': 0,
                'skipped': 0,
                'difficulty_counts': {'easy': 0, 'medium': 0, 'hard': 0},
                'bloom_counts': {}
            }
            
            logger.info(f"🔄 بدء تصنيف {len(questions)} سؤال (تأخير {self.min_delay}s)...")
            
            for i, question in enumerate(questions):
                # توقف إذا كان هناك أخطاء متتالية كثيرة
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.warning(f"⚠️ توقف بسبب {self.consecutive_errors} أخطاء متتالية")
                    break
                
                try:
                    q_text = question.question_text or ""
                    
                    # تخطي الأسئلة الفارغة
                    if not q_text.strip():
                        stats['skipped'] += 1
                        logger.info(f"  ⏭️ [{i+1}/{len(questions)}] Q{question.question_id}: تخطي (سؤال بالصورة)")
                        continue
                    
                    options = []
                    if question.options:
                        options = [opt.option_text for opt in question.options if opt.option_text]
                    
                    classification = self.classify_question(q_text, options)
                    
                    # تخطي إذا تم التخطي
                    if classification.get('skipped'):
                        stats['skipped'] += 1
                        continue
                    
                    # فشل - سجل واستمر
                    if classification.get('error'):
                        stats['failed'] += 1
                        logger.warning(f"  ⚠️ [{i+1}/{len(questions)}] Q{question.question_id}: {classification.get('error', 'فشل')[:30]}")
                        continue
                    
                    # نجاح - حفظ التصنيف
                    question.difficulty = classification['difficulty']
                    question.bloom_level = classification['bloom_level']
                    
                    # ✅ تحديث ai_classified باستخدام raw SQL
                    try:
                        from sqlalchemy import text
                        db.session.execute(
                            text("UPDATE questions SET ai_classified = TRUE WHERE question_id = :qid"),
                            {"qid": question.question_id}
                        )
                    except Exception as sql_err:
                        logger.debug(f"تعذر تحديث ai_classified: {sql_err}")
                    
                    stats['classified'] += 1
                    stats['difficulty_counts'][classification['difficulty']] += 1
                    bloom = classification['bloom_level']
                    stats['bloom_counts'][bloom] = stats['bloom_counts'].get(bloom, 0) + 1
                    
                    logger.info(f"  ✅ [{i+1}/{len(questions)}] Q{question.question_id}: {classification['difficulty']}, {classification['bloom_level']}")
                    
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"  ❌ [{i+1}/{len(questions)}] Q{question.question_id}: {str(e)[:30]}")
                    # لا نتوقف - نستمر للسؤال التالي
                    continue
            
            # حفظ التغييرات
            try:
                db.session.commit()
                logger.info("💾 تم حفظ التصنيفات في قاعدة البيانات")
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ خطأ في الحفظ: {e}")
                return {'success': False, 'error': f'خطأ في الحفظ: {str(e)[:50]}'}
            
            # إعداد النتيجة
            stats['success'] = True
            if stats['classified'] > 0:
                stats['message'] = f"✅ تم تصنيف {stats['classified']} من {stats['total']} سؤال"
            elif stats['failed'] > 0:
                stats['message'] = f"⚠️ فشل تصنيف {stats['failed']} سؤال"
            else:
                stats['message'] = f"⏭️ تم تخطي {stats['skipped']} سؤال (بالصورة)"
            
            logger.info(f"📊 {stats['message']}")
            if stats['classified'] > 0:
                logger.info(f"   الصعوبة: {stats['difficulty_counts']}")
                logger.info(f"   بلوم: {stats['bloom_counts']}")
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ خطأ عام: {e}")
            return {'success': False, 'error': str(e)[:100]}
    
    def get_classification_stats(self) -> Dict:
        """إحصائيات التصنيف"""
        if Question is None:
            return {'error': 'Question model not available'}
        
        try:
            total = Question.query.count()
            
            # عدد المصنفة (ليست medium/remember الافتراضية)
            classified = Question.query.filter(
                db.and_(
                    Question.difficulty != None,
                    Question.difficulty != 'medium',
                    Question.bloom_level != None,
                    Question.bloom_level != 'remember'
                )
            ).count()
            
            difficulty_stats = db.session.query(
                Question.difficulty, db.func.count(Question.question_id)
            ).group_by(Question.difficulty).all()
            
            bloom_stats = db.session.query(
                Question.bloom_level, db.func.count(Question.question_id)
            ).group_by(Question.bloom_level).all()
            
            return {
                'total_questions': total,
                'classified_count': classified,
                'remaining': total - classified,
                'by_difficulty': {d or 'unset': c for d, c in difficulty_stats},
                'by_bloom_level': {b or 'unset': c for b, c in bloom_stats}
            }
        except Exception as e:
            return {'error': str(e)}


question_classifier = QuestionClassifier()
