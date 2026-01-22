# src/services/question_classifier.py
"""
خدمة تصنيف الأسئلة بالذكاء الاصطناعي (Gemini)
===============================================

الاستخدام:
    from src.services.question_classifier import question_classifier
    
    # تصنيف سؤال واحد
    result = question_classifier.classify_question(question_text, options)
    
    # تصنيف كل الأسئلة غير المصنفة
    question_classifier.classify_all_unclassified()
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

# إعداد logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuestionClassifier:
    """خدمة تصنيف الأسئلة بالذكاء الاصطناعي"""
    
    def __init__(self):
        """تهيئة أولية فارغة"""
        self.model = None
        self.is_configured = False
        self.api_key = None
        self.model_name = 'gemini-2.0-flash-exp'  # نفس الموديل المستخدم في ai_assistant
    
    def _ensure_configured(self) -> bool:
        """تهيئة Gemini عند الحاجة (Lazy Loading)"""
        if self.is_configured and self.model:
            return True
        
        try:
            # جلب المفتاح
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
            logger.info("✅ تم تهيئة Gemini لتصنيف الأسئلة")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Gemini: {e}")
            return False
    
    def classify_question(self, question_text: str, options: List[str] = None) -> Dict:
        """
        تصنيف سؤال واحد
        
        Args:
            question_text: نص السؤال
            options: قائمة الخيارات (اختياري)
        
        Returns:
            dict: {'difficulty': 'easy/medium/hard', 'bloom_level': 'remember/understand/...'}
        """
        if not self._ensure_configured():
            return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'AI not configured'}
        
        try:
            # بناء prompt التصنيف
            prompt = self._build_classification_prompt(question_text, options)
            
            # استدعاء AI
            response = self.model.generate_content(prompt)
            
            # تحليل الرد
            result = self._parse_classification_response(response.text)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ خطأ في تصنيف السؤال: {e}")
            return {'difficulty': 'medium', 'bloom_level': 'remember', 'error': str(e)}
    
    def _build_classification_prompt(self, question_text: str, options: List[str] = None) -> str:
        """بناء prompt التصنيف"""
        
        options_text = ""
        if options:
            options_text = "\nالخيارات:\n" + "\n".join([f"- {opt}" for opt in options])
        
        return f"""
أنت خبير في تصنيف أسئلة الكيمياء التعليمية.

صنّف السؤال التالي:

السؤال: {question_text}
{options_text}

---

صنّف السؤال حسب معيارين:

1. **الصعوبة** (اختر واحد فقط):
   - easy: سؤال مباشر، تعريف بسيط، حقيقة واضحة، لا يحتاج تفكير
   - medium: تطبيق قانون، حساب بسيط، فهم مفهوم، ربط معلومتين
   - hard: حسابات معقدة، ربط عدة مفاهيم، تحليل عميق، مسائل متعددة الخطوات

2. **مستوى بلوم** (اختر واحد فقط):
   - remember: تذكر واسترجاع - "اذكر"، "عرّف"، "سمّ"، "ما هو"، "متى"
   - understand: فهم واستيعاب - "اشرح"، "وضّح"، "فسّر"، "لماذا"، "ما الفرق"
   - apply: تطبيق - "احسب"، "طبّق"، "استخدم"، "أوجد"، "حل"
   - analyze: تحليل - "قارن"، "حلل"، "ما العلاقة"، "صنّف"، "ميّز"
   - evaluate: تقويم - "قيّم"، "احكم"، "أيهما أفضل"، "برر"، "انتقد"
   - create: إبداع - "صمم"، "اقترح"، "ماذا لو"، "ابتكر"

---

أجب بصيغة JSON فقط بدون أي نص إضافي:
{{"difficulty": "easy/medium/hard", "bloom_level": "remember/understand/apply/analyze/evaluate/create"}}
"""
    
    def _parse_classification_response(self, response_text: str) -> Dict:
        """تحليل رد AI واستخراج التصنيف"""
        
        # القيم الافتراضية
        result = {
            'difficulty': 'medium',
            'bloom_level': 'remember'
        }
        
        try:
            # محاولة استخراج JSON
            import re
            json_match = re.search(r'\{[^}]+\}', response_text)
            
            if json_match:
                parsed = json.loads(json_match.group())
                
                # التحقق من القيم الصحيحة
                valid_difficulties = ['easy', 'medium', 'hard']
                valid_blooms = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']
                
                if parsed.get('difficulty') in valid_difficulties:
                    result['difficulty'] = parsed['difficulty']
                
                if parsed.get('bloom_level') in valid_blooms:
                    result['bloom_level'] = parsed['bloom_level']
            
        except json.JSONDecodeError:
            logger.warning(f"⚠️ فشل تحليل JSON: {response_text[:100]}")
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تحليل الرد: {e}")
        
        return result
    
    def classify_all_unclassified(self, batch_size: int = 50, delay: float = 0.5) -> Dict:
        """
        تصنيف كل الأسئلة غير المصنفة (التي لها القيم الافتراضية)
        
        Args:
            batch_size: عدد الأسئلة في كل دفعة
            delay: التأخير بين الطلبات (ثانية) لتجنب rate limiting
        
        Returns:
            dict: إحصائيات التصنيف
        """
        if not self._ensure_configured():
            return {'success': False, 'error': 'AI not configured'}
        
        if Question is None:
            return {'success': False, 'error': 'Question model not available'}
        
        try:
            # جلب الأسئلة غير المصنفة (القيم الافتراضية)
            questions = Question.query.filter(
                (Question.difficulty == 'medium') | (Question.difficulty == None),
                (Question.bloom_level == 'remember') | (Question.bloom_level == None)
            ).limit(batch_size).all()
            
            if not questions:
                return {
                    'success': True,
                    'message': 'لا توجد أسئلة تحتاج تصنيف',
                    'classified': 0
                }
            
            stats = {
                'total': len(questions),
                'classified': 0,
                'failed': 0,
                'difficulty_counts': {'easy': 0, 'medium': 0, 'hard': 0},
                'bloom_counts': {}
            }
            
            logger.info(f"🔄 بدء تصنيف {len(questions)} سؤال...")
            
            for i, question in enumerate(questions):
                try:
                    # جمع نص السؤال والخيارات
                    q_text = question.question_text or "[سؤال بالصورة]"
                    options = [opt.option_text for opt in question.options if opt.option_text]
                    
                    # تصنيف السؤال
                    classification = self.classify_question(q_text, options)
                    
                    if 'error' not in classification:
                        # تحديث السؤال
                        question.difficulty = classification['difficulty']
                        question.bloom_level = classification['bloom_level']
                        
                        stats['classified'] += 1
                        stats['difficulty_counts'][classification['difficulty']] += 1
                        stats['bloom_counts'][classification['bloom_level']] = \
                            stats['bloom_counts'].get(classification['bloom_level'], 0) + 1
                        
                        logger.info(f"  ✅ [{i+1}/{len(questions)}] Q{question.question_id}: {classification['difficulty']}, {classification['bloom_level']}")
                    else:
                        stats['failed'] += 1
                        logger.warning(f"  ⚠️ [{i+1}/{len(questions)}] Q{question.question_id}: {classification['error']}")
                    
                    # تأخير لتجنب rate limiting
                    if delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"  ❌ [{i+1}/{len(questions)}] Q{question.question_id}: {e}")
            
            # حفظ التغييرات
            db.session.commit()
            
            stats['success'] = True
            stats['message'] = f"تم تصنيف {stats['classified']} من {stats['total']} سؤال"
            
            logger.info(f"✅ انتهى التصنيف: {stats['message']}")
            logger.info(f"   الصعوبة: {stats['difficulty_counts']}")
            logger.info(f"   بلوم: {stats['bloom_counts']}")
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ خطأ في classify_all_unclassified: {e}")
            return {'success': False, 'error': str(e)}
    
    def classify_question_on_save(self, question: 'Question') -> bool:
        """
        تصنيف سؤال تلقائياً عند الحفظ
        يُستدعى من route إضافة/تعديل السؤال
        
        Args:
            question: كائن السؤال
        
        Returns:
            bool: نجاح التصنيف
        """
        try:
            # إذا السؤال مصنف يدوياً، لا تغير
            if question.difficulty and question.difficulty != 'medium':
                return True
            if question.bloom_level and question.bloom_level != 'remember':
                return True
            
            # جمع البيانات
            q_text = question.question_text or "[سؤال بالصورة]"
            options = [opt.option_text for opt in question.options if opt.option_text]
            
            # تصنيف
            classification = self.classify_question(q_text, options)
            
            if 'error' not in classification:
                question.difficulty = classification['difficulty']
                question.bloom_level = classification['bloom_level']
                logger.info(f"✅ تصنيف تلقائي Q{question.question_id}: {classification}")
                return True
            else:
                logger.warning(f"⚠️ فشل التصنيف التلقائي: {classification['error']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ خطأ في classify_question_on_save: {e}")
            return False
    
    def get_classification_stats(self) -> Dict:
        """الحصول على إحصائيات التصنيف الحالية"""
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
            logger.error(f"❌ خطأ في get_classification_stats: {e}")
            return {'error': str(e)}


# إنشاء instance واحد
question_classifier = QuestionClassifier()
