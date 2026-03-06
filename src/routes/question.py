import os
import logging
import time
import uuid
import io # Added for reading/writing file in memory
import json
import pandas as pd # Added for reading Excel/CSV
from datetime import datetime
import random
import copy
import qrcode
import base64
import barcode
from barcode.writer import ImageWriter
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app,
    send_file, jsonify # Added for sending generated files
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager
from flask_wtf import FlaskForm # إضافة استيراد FlaskForm

# Import Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

try:
    from src.extensions import db
except ImportError:  # pragma: no cover
    try:
        from extensions import db
    except ImportError:
        print("Warning: Could not import db from src.extensions or extensions. Trying from main.")
        try:
            from main import db
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            raise

try:
    from src.models.question import Question, Option
    from src.models.curriculum import Lesson, Unit, Course
    from src.models.activity import Activity  # استيراد نموذج النشاط
except ImportError:  # pragma: no cover
    try:
        from models.question import Question, Option
        from models.curriculum import Lesson, Unit, Course
        from models.activity import Activity  # استيراد نموذج النشاط
    except ImportError:
        print("Error: Could not import models.")
        raise


class ExamHeaderSettings(db.Model):
    __tablename__ = 'exam_header_settings'
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(255), default='المملكة العربية السعودية')
    ministry = db.Column(db.String(255), default='وزارة التعليم')
    education_department = db.Column(db.String(255), default='الإدارة العامة للتعليم بالمنطقة الشرقية')
    school_name = db.Column(db.String(255), default='مدرسة عبدالرحمن بن القاسم الثانوية')
    subject = db.Column(db.String(255), default='كيمياء 4')
    time = db.Column(db.String(255), default='ثلاث ساعات')
    grade = db.Column(db.String(255), default='ثالث ثانوي')
    total_score = db.Column(db.Integer, default=30)
    checker_name = db.Column(db.String(255), nullable=True)
    reviewer_name = db.Column(db.String(255), nullable=True)
    exam_date = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ExamHeaderSettings {self.id}>"


class SavedExam(db.Model):
    """نموذج لحفظ الاختبارات المولدة"""
    __tablename__ = 'saved_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    course_id = db.Column(db.Integer, nullable=True)  # بدون ForeignKey لتجنب مشاكل العلاقات
    unit_id = db.Column(db.Integer, nullable=True)
    question_ids = db.Column(db.JSON, nullable=False, default=list)
    questions_count = db.Column(db.Integer, nullable=False, default=0)
    models = db.Column(db.JSON, default=['أ'])
    settings = db.Column(db.JSON, default=dict)
    header_settings = db.Column(db.JSON, default=dict)
    exam_type = db.Column(db.String(50), nullable=True)
    semester = db.Column(db.String(50), nullable=True)
    academic_year = db.Column(db.String(50), nullable=True)
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def get_course_name(self):
        """جلب اسم المنهج"""
        if self.course_id:
            course = Course.query.get(self.course_id)
            return course.name if course else None
        return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'course_id': self.course_id,
            'course_name': self.get_course_name(),
            'unit_id': self.unit_id,
            'question_ids': self.question_ids,
            'questions_count': self.questions_count,
            'models': self.models,
            'settings': self.settings,
            'header_settings': self.header_settings,
            'exam_type': self.exam_type,
            'semester': self.semester,
            'academic_year': self.academic_year,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<SavedExam {self.id}: {self.name}>"


# إضافة استيراد نظام الإشعارات
try:
    from src.utils.notification_system import QuestionNotifications, SystemNotifications
    notifications_available = True
except ImportError:  # pragma: no cover
    try:
        from utils.notification_system import QuestionNotifications, SystemNotifications
        notifications_available = True
    except ImportError:
        print("Warning: Could not import notification system for questions")
        QuestionNotifications = None
        SystemNotifications = None
        notifications_available = False

question_bp = Blueprint("question", __name__, template_folder="../templates/question")

# === دوال مساعدة للإشعارات ===

def notify_question_operation(operation_type, lesson_name=None, question_text=None, count=1):
    """
    دالة مساعدة موحدة لإرسال إشعارات عمليات الأسئلة
    دالة مساعدة موحدة لإرسال إشعارات عمليات الأسئلة
    """
    if not notifications_available or not QuestionNotifications:
        return
    
    try:
        if operation_type == "add":
            QuestionNotifications.notify_question_added(
                lesson_name=lesson_name or "درس غير محدد",
                question_text=question_text or "سؤال جديد",
                user_id=current_user.id
            )
        elif operation_type == "update":
            QuestionNotifications.notify_question_updated(
                lesson_name=lesson_name or "درس غير محدد",
                question_text=question_text or "سؤال محدث",
                user_id=current_user.id
            )
        elif operation_type == "delete":
            QuestionNotifications.notify_question_deleted(
                lesson_name=lesson_name or "درس غير محدد",
                user_id=current_user.id
            )
        elif operation_type == "import":
            QuestionNotifications.notify_questions_imported(
                count=count,
                lesson_name=lesson_name or "دروس متعددة",
                user_id=current_user.id
            )
            
        current_app.logger.info(f"Question {operation_type} notification sent successfully")
        
    except Exception as e:
        current_app.logger.error(f"Error sending question {operation_type} notification: {e}")

def notify_system_operation(operation_type, details=None, count=None):
    """
    دالة مساعدة موحدة لإرسال إشعارات عمليات النظام
    """
    if not notifications_available or not SystemNotifications:
        return
    
    try:
        if operation_type == "export":
            SystemNotifications.notify_data_export(
                export_type=details or "بيانات",
                count=count or 0,
                user_id=current_user.id
            )
        elif operation_type == "upload":
            SystemNotifications.notify_file_upload(
                filename=details or "ملف",
                subfolder="questions",
                user_id=current_user.id
            )
        elif operation_type == "api_usage":
            SystemNotifications.notify_api_usage(
                endpoint=details or "unknown",
                user_id=current_user.id
            )
            
        current_app.logger.info(f"System {operation_type} notification sent successfully")
        
    except Exception as e:
        current_app.logger.error(f"Error sending system {operation_type} notification: {e}")

# Allowed extensions for image uploads
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
# Allowed extensions for question import files
ALLOWED_IMPORT_EXTENSIONS = {"xlsx", "csv"}

# Define expected columns for import template (used in import and download)
EXPECTED_IMPORT_COLUMNS = [
    "Course Name", "Unit Name", "Lesson Name",
    "Question Text", "Question Image URL",
    "Option 1 Text", "Option 1 Image URL",
    "Option 2 Text", "Option 2 Image URL",
    "Option 3 Text", "Option 3 Image URL",
    "Option 4 Text", "Option 4 Image URL",
    "Correct Option Number",
    "Explanation"
]

def allowed_image_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS)

def allowed_import_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMPORT_EXTENSIONS)


# === دالة تنسيق النص للطباعة (تحويل الأسطر الجديدة) ===
from markupsafe import Markup, escape

def format_text_for_print(text):
    """
    تنسيق النص للطباعة:
    - تحويل السطور الجديدة (\n) إلى <br>
    - هذا يضمن أن كل سطر يظهر كما أدخله المعلم
    
    ملاحظة: لا نستخدم white-space: nowrap لأنه يسبب خروج النص من العمود
    """
    if not text:
        return ''
    
    # أولاً: escape أي HTML موجود في النص الأصلي (للأمان)
    safe_text = str(escape(text))
    
    # ثانياً: تحويل السطور الجديدة إلى <br>
    formatted = safe_text.replace('\n', '<br>')
    
    # إرجاع كـ Markup لمنع escape مرة أخرى في القالب
    return Markup(formatted)


def get_ordered_questions(question_ids):
    """
    جلب الأسئلة مرتبة حسب الوحدة ثم الدرس (باستخدام order_num)
    """
    if not question_ids:
        return []
    
    try:
        # جلب الأسئلة مرتبة حسب ترتيب الوحدة ثم الدرس
        questions = Question.query.filter(
            Question.question_id.in_(question_ids)
        ).join(
            Lesson, Question.lesson_id == Lesson.id
        ).join(
            Unit, Lesson.unit_id == Unit.id
        ).order_by(
            Unit.order_num,
            Unit.id,
            Lesson.order_num,
            Lesson.id,
            Question.question_id
        ).all()
        return questions
    except Exception:
        # في حالة فشل الترتيب، نرجع الأسئلة بدون ترتيب
        return Question.query.filter(Question.question_id.in_(question_ids)).all()


# --- save_upload function (Modified for Cloudinary) --- #
def save_upload(file, subfolder="questions"):
    current_app.logger.debug(f"Entering save_upload for Cloudinary, subfolder: {subfolder}")
    if not file or not file.filename:
        current_app.logger.debug("No file or filename provided to save_upload.")
        return None

    current_app.logger.debug(f"Processing file: {file.filename}")

    if not allowed_image_file(file.filename):
        current_app.logger.warning(f"Image file type not allowed: {file.filename}")
        return None
    
    current_app.logger.debug(f"Image file type allowed for: {file.filename}")

    # Configure Cloudinary (should ideally be done once at app startup)
    # Ensure CLOUDINARY_URL or individual CLOUD_NAME, API_KEY, API_SECRET are set in environment
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
         current_app.logger.error("Cloudinary environment variables (CLOUD_NAME, API_KEY, API_SECRET) are missing or incomplete.")
         # Attempt to configure from CLOUDINARY_URL as a fallback
         if os.environ.get("CLOUDINARY_URL"):
             current_app.logger.info("Attempting to configure Cloudinary from CLOUDINARY_URL.")
             try:
                 cloudinary.config()
                 current_app.logger.info("Cloudinary configured from URL.")
             except Exception as config_err:
                 current_app.logger.error(f"Failed to configure Cloudinary from URL: {config_err}")
                 return None
         else:
             current_app.logger.error("CLOUDINARY_URL is also missing.")
             return None
    else:
        try:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            current_app.logger.debug("Cloudinary configured from individual variables.")
        except Exception as config_err:
            current_app.logger.error(f"Failed to configure Cloudinary from individual variables: {config_err}")
            return None

    try:
        original_filename = secure_filename(file.filename)
        # Generate a unique public_id using timestamp and UUID
        public_id = f"{subfolder}/{int(time.time())}_{uuid.uuid4().hex[:8]}_{os.path.splitext(original_filename)[0]}"
        current_app.logger.debug(f"Generated Cloudinary public_id: {public_id}")

        current_app.logger.debug(f"Attempting to upload to Cloudinary with public_id: {public_id}")
        
        # Ensure file pointer is at the beginning
        file.seek(0)
        
        upload_result = cloudinary.uploader.upload(
            file.stream, # Pass the file stream
            public_id=public_id,
            folder=subfolder, # Optional: Organize within Cloudinary folders
            resource_type="auto" # Automatically detect resource type (image/video/raw)
        )
        current_app.logger.debug("Cloudinary upload call completed.")

        if upload_result and upload_result.get("secure_url"):
            image_url = upload_result["secure_url"]
            current_app.logger.info(f"File uploaded successfully to Cloudinary: {image_url}")
            
            # === إضافة إشعار رفع الصورة ===
            if notifications_available and SystemNotifications:
                try:
                    SystemNotifications.notify_file_upload(
                        filename=original_filename,
                        subfolder=subfolder,
                        user_id=getattr(current_user, 'id', None)
                    )
                except Exception as e:
                    current_app.logger.error(f"Error sending file upload notification: {e}")
            
            return image_url
        else:
            error_message = upload_result.get("error", {}).get("message", "Unknown error") if upload_result else "No response"
            current_app.logger.error(f"Cloudinary upload failed: {error_message}")
            current_app.logger.debug(f"Cloudinary upload response: {upload_result}")
            return None

    except Exception as e:
        current_app.logger.error(f"Exception during Cloudinary upload process: {e}", exc_info=True)
        return None

# --- list_questions route (keep as is) --- #
@question_bp.route("/")
@login_required
def list_questions():
    current_app.logger.info("Entering list_questions route.")
    
    # استقبال معاملات التصفية من الطلب
    course_id = request.args.get("course_id", type=int)
    unit_id = request.args.get("unit_id", type=int)
    lesson_id = request.args.get("lesson_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = 9
    
    current_app.logger.info(f"Filter parameters: course_id={course_id}, unit_id={unit_id}, lesson_id={lesson_id}, page={page}")
    
    try:
        # بناء الاستعلام الأساسي مع ضمان جلب جميع العلاقات
        query = Question.query.options(
            joinedload(Question.options),  # جلب خيارات السؤال
            joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
        )
        
        # إضافة شروط التصفية بطريقة محسنة لتجنب تداخل الـ joins
        if lesson_id:
            # التصفية حسب الدرس - مباشرة بدون join إضافي
            query = query.filter(Question.lesson_id == lesson_id)
            current_app.logger.info(f"Filtering by lesson_id: {lesson_id}")
        elif unit_id:
            # التصفية حسب الوحدة - استخدام exists بدلاً من join
            query = query.filter(Question.lesson.has(Lesson.unit_id == unit_id))
            current_app.logger.info(f"Filtering by unit_id: {unit_id}")
        elif course_id:
            # التصفية حسب المنهج - استخدام exists بدلاً من join متعدد
            query = query.filter(Question.lesson.has(Lesson.unit.has(Unit.course_id == course_id)))
            current_app.logger.info(f"Filtering by course_id: {course_id}")
        
        # ترتيب النتائج وتقسيمها إلى صفحات
        questions_pagination = query.order_by(Question.question_id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")
        
        # التحقق من جلب الخيارات بشكل صحيح
        for question in questions_pagination.items:
            options_count = len(question.options) if question.options else 0
            current_app.logger.info(f"Question {question.question_id} has {options_count} options")
        
        # جلب قوائم الدورات والوحدات والدروس للتصفية
        courses = Course.query.order_by(Course.name).all()
        units = []
        lessons = []
        
        if course_id:
            units = Unit.query.filter_by(course_id=course_id).order_by(Unit.name).all()
            if unit_id:
                lessons = Lesson.query.filter_by(unit_id=unit_id).order_by(Lesson.name).all()
        
        rendered_template = render_template(
            "question/list.html", 
            questions=questions_pagination.items, 
            pagination=questions_pagination,
            courses=courses,
            units=units,
            lessons=lessons,
            page=page,
            per_page=per_page
        )
        
        current_app.logger.info("Template rendering successful.")
        return rendered_template
        
    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash("حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
        return redirect(url_for("index"))

# --- دوال التصدير المتقدم ---

def apply_filters(query, filters):
    """
    تطبيق التصفيات على الاستعلام
    """
    if not filters:
        return query
    
    for filter_item in filters:
        field = filter_item.get('field')
        operator = filter_item.get('operator')
        value = filter_item.get('value')
        
        if not field or not operator or not value:
            continue
            
        try:
            if field == 'course':
                if operator == 'equals':
                    query = query.join(Question.lesson).join(Lesson.unit).join(Unit.course).filter(Course.name == value)
                elif operator == 'contains':
                    query = query.join(Question.lesson).join(Lesson.unit).join(Unit.course).filter(Course.name.contains(value))
                elif operator == 'starts_with':
                    query = query.join(Question.lesson).join(Lesson.unit).join(Unit.course).filter(Course.name.startswith(value))
                elif operator == 'ends_with':
                    query = query.join(Question.lesson).join(Lessons.unit).join(Unit.course).filter(Course.name.endswith(value))
                    
            elif field == 'unit':
                if operator == 'equals':
                    query = query.join(Question.lesson).join(Lesson.unit).filter(Unit.name == value)
                elif operator == 'contains':
                    query = query.join(Question.lesson).join(Lesson.unit).filter(Unit.name.contains(value))
                elif operator == 'starts_with':
                    query = query.join(Question.lesson).join(Lesson.unit).filter(Unit.name.startswith(value))
                elif operator == 'ends_with':
                    query = query.join(Question.lesson).join(Lesson.unit).filter(Unit.name.endswith(value))
                    
            elif field == 'lesson':
                if operator == 'equals':
                    query = query.join(Question.lesson).filter(Lesson.name == value)
                elif operator == 'contains':
                    query = query.join(Question.lesson).filter(Lesson.name.contains(value))
                elif operator == 'starts_with':
                    query = query.join(Question.lesson).filter(Lesson.name.startswith(value))
                elif operator == 'ends_with':
                    query = query.join(Question.lesson).filter(Lesson.name.endswith(value))
                    
            elif field == 'question_text':
                if operator == 'equals':
                    query = query.filter(Question.question_text == value)
                elif operator == 'contains':
                    query = query.filter(Question.question_text.contains(value))
                elif operator == 'starts_with':
                    query = query.filter(Question.question_text.startswith(value))
                elif operator == 'ends_with':
                    query = query.filter(Question.question_text.endswith(value))
                    
            elif field == 'created_at':
                try:
                    date_value = datetime.strptime(value, '%Y-%m-%d')
                    if operator == 'equals':
                        query = query.filter(db.func.date(Question.created_at) == date_value.date())
                    elif operator == 'greater_than':
                        query = query.filter(Question.created_at > date_value)
                    elif operator == 'less_than':
                        query = query.filter(Question.created_at < date_value)
                except ValueError:
                    current_app.logger.warning(f"Invalid date format for filter: {value}")
                    continue
                    
        except Exception as e:
            current_app.logger.error(f"Error applying filter {field} {operator} {value}: {e}")
            continue
            
    return query

def prepare_template_export_data(filters=None):
    """
    تحضير البيانات للتصدير وفقاً لتنسيق قالب الاستيراد مع إضافة ميزة الشرح
    """
    try:
        # جلب الأسئلة مع التفاصيل
        query = Question.query.options(
            joinedload(Question.options),
            joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
        )
        
        # تطبيق التصفيات
        if filters:
            query = apply_filters(query, filters)
        
        questions = query.all()
        
        # تحضير البيانات
        data = []
        for question in questions:
            row = {}
            
            # معلومات المنهج والوحدة والدرس
            row['Course Name'] = question.lesson.unit.course.name if question.lesson and question.lesson.unit and question.lesson.unit.course else ''
            row['Unit Name'] = question.lesson.unit.name if question.lesson and question.lesson.unit else ''
            row['Lesson Name'] = question.lesson.name if question.lesson else ''
            
            # نص السؤال وصورته
            row['Question Text'] = question.question_text or ''
            row['Question Image URL'] = question.image_url or ''
            
            # الخيارات مع صورها
            options = list(question.options)
            for i in range(1, 5):  # دعم حتى 4 خيارات
                if i <= len(options):
                    row[f'Option {i} Text'] = options[i-1].option_text or ''
                    row[f'Option {i} Image URL'] = options[i-1].image_url or ''
                else:
                    row[f'Option {i} Text'] = ''
                    row[f'Option {i} Image URL'] = ''
            
            # رقم الخيار الصحيح
            correct_option_number = ''
            for i, option in enumerate(question.options, 1):
                if option.is_correct:
                    correct_option_number = str(i)
                    break
            row['Correct Option Number'] = correct_option_number
            
            # الشرح (الميزة الجديدة)
            row['Explanation'] = question.explanation or ''
            
            data.append(row)
        
        return data
        
    except Exception as e:
        current_app.logger.error(f"Error preparing template export data: {e}")
        return []

def prepare_export_data(data_type, selected_fields, filters=None):
    """
    تحضير البيانات للتصدير بناءً على النوع والحقول المختارة والتصفيات
    """
    try:
        if data_type == 'questions':
            # جلب الأسئلة مع التفاصيل
            query = Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            )
            
            # تطبيق التصفيات
            if filters:
                query = apply_filters(query, filters)
            
            questions = query.all()
            
            # تحضير البيانات
            data = []
            for question in questions:
                row = {}
                
                if 'course' in selected_fields:
                    row['المنهج'] = question.lesson.unit.course.name if question.lesson and question.lesson.unit and question.lesson.unit.course else ''
                if 'unit' in selected_fields:
                    row['الوحدة'] = question.lesson.unit.name if question.lesson and question.lesson.unit else ''
                if 'lesson' in selected_fields:
                    row['الدرس'] = question.lesson.name if question.lesson else ''
                if 'question_text' in selected_fields:
                    row['نص السؤال'] = question.question_text or ''
                if 'question_image' in selected_fields:
                    row['صورة السؤال'] = question.image_url or ''
                if 'options' in selected_fields:
                    # فصل الخيارات في أعمدة منفصلة
                    options = list(question.options)
                    for i in range(1, 5):  # دعم حتى 4 خيارات
                        if i <= len(options):
                            row[f'الخيار {i}'] = options[i-1].option_text or ''
                        else:
                            row[f'الخيار {i}'] = ''
                if 'correct_answer' in selected_fields:
                    # إضافة رقم الإجابة الصحيحة ونص الإجابة
                    correct_option_number = ''
                    correct_option_text = ''
                    for i, option in enumerate(question.options, 1):
                        if option.is_correct:
                            correct_option_number = str(i)
                            correct_option_text = option.option_text or ''
                            break
                    row['رقم الإجابة الصحيحة'] = correct_option_number
                    row['الإجابة الصحيحة'] = correct_option_text
                if 'explanation' in selected_fields:
                    row['الشرح'] = question.explanation or ''
                if 'created_at' in selected_fields:
                    row['تاريخ الإنشاء'] = question.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(question, 'created_at') and question.created_at else ''
                
                data.append(row)
                
        elif data_type == 'curriculum':
            # جلب هيكل المنهج
            courses = Course.query.options(
                joinedload(Course.units).joinedload(Unit.lessons)
            ).all()
            
            data = []
            for course in courses:
                if 'course' in selected_fields:
                    course_row = {
                        'النوع': 'منهج',
                        'الاسم': course.name,
                        'المنهج': course.name,
                        'الوحدة': '',
                        'الدرس': '',
                        'عدد الوحدات': len(course.units),
                        'عدد الدروس': sum(len(unit.lessons) for unit in course.units),
                        'عدد الأسئلة': sum(len(lesson.questions) for unit in course.units for lesson in unit.lessons)
                    }
                    data.append(course_row)
                
                for unit in course.units:
                    if 'unit' in selected_fields:
                        unit_row = {
                            'النوع': 'وحدة',
                            'الاسم': unit.name,
                            'المنهج': course.name,
                            'الوحدة': unit.name,
                            'الدرس': '',
                            'عدد الوحدات': '',
                            'عدد الدروس': len(unit.lessons),
                            'عدد الأسئلة': sum(len(lesson.questions) for lesson in unit.lessons)
                        }
                        data.append(unit_row)
                    
                    for lesson in unit.lessons:
                        if 'lesson' in selected_fields:
                            lesson_row = {
                                'النوع': 'درس',
                                'الاسم': lesson.name,
                                'المنهج': course.name,
                                'الوحدة': unit.name,
                                'الدرس': lesson.name,
                                'عدد الوحدات': '',
                                'عدد الدروس': '',
                                'عدد الأسئلة': len(lesson.questions)
                            }
                            data.append(lesson_row)
                            
        else:  # all data
            # جلب جميع البيانات
            query = Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            )
            
            # تطبيق التصفيات
            if filters:
                query = apply_filters(query, filters)
            
            questions = query.all()
            
            data = []
            for question in questions:
                row = {}
                
                if 'course' in selected_fields:
                    row['المنهج'] = question.lesson.unit.course.name if question.lesson and question.lesson.unit and question.lesson.unit.course else ''
                if 'unit' in selected_fields:
                    row['الوحدة'] = question.lesson.unit.name if question.lesson and question.lesson.unit else ''
                if 'lesson' in selected_fields:
                    row['الدرس'] = question.lesson.name if question.lesson else ''
                if 'question_text' in selected_fields:
                    row['نص السؤال'] = question.question_text or ''
                if 'question_image' in selected_fields:
                    row['صورة السؤال'] = question.image_url or ''
                if 'options' in selected_fields:
                    # فصل الخيارات في أعمدة منفصلة
                    options = list(question.options)
                    for i in range(1, 5):  # دعم حتى 4 خيارات
                        if i <= len(options):
                            row[f'الخيار {i}'] = options[i-1].option_text or ''
                        else:
                            row[f'الخيار {i}'] = ''
                if 'correct_answer' in selected_fields:
                    # إضافة رقم الإجابة الصحيحة ونص الإجابة
                    correct_option_number = ''
                    correct_option_text = ''
                    for i, option in enumerate(question.options, 1):
                        if option.is_correct:
                            correct_option_number = str(i)
                            correct_option_text = option.option_text or ''
                            break
                    row['رقم الإجابة الصحيحة'] = correct_option_number
                    row['الإجابة الصحيحة'] = correct_option_text
                if 'explanation' in selected_fields:
                    row['الشرح'] = question.explanation or ''
                if 'created_at' in selected_fields:
                    row['تاريخ الإنشاء'] = question.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(question, 'created_at') and question.created_at else ''
                
                data.append(row)
        
        return data
        
    except Exception as e:
        current_app.logger.error(f"Error preparing export data: {e}")
        return []

@question_bp.route("/export/template_format", methods=["POST"])
@login_required
def export_template_format():
    """
    تصدير البيانات بتنسيق قالب الاستيراد مع إضافة ميزة الشرح
    """
    try:
        # استقبال التصفيات
        filter_fields = request.form.getlist('filter_field[]')
        filter_operators = request.form.getlist('filter_operator[]')
        filter_values = request.form.getlist('filter_value[]')
        
        # تحضير قائمة التصفيات
        filters = []
        for i in range(len(filter_fields)):
            if i < len(filter_operators) and i < len(filter_values):
                if filter_fields[i] and filter_operators[i] and filter_values[i]:
                    filters.append({
                        'field': filter_fields[i],
                        'operator': filter_operators[i],
                        'value': filter_values[i]
                    })
        
        # تحضير البيانات بتنسيق القالب
        data = prepare_template_export_data(filters)
        
        if not data:
            flash("لا توجد بيانات للتصدير بناءً على التصفيات المحددة.", "warning")
            return redirect(url_for("dashboard"))
        
        # إنشاء DataFrame
        df = pd.DataFrame(data)
        
        # تحضير اسم الملف
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"questions_template_format_{timestamp}.xlsx"
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Questions')
        output.seek(0)
        
        # تسجيل النشاط
        try:
            activity = Activity(
                user_id=current_user.id,
                action="تصدير البيانات",
                description=f"تم تصدير {len(data)} سؤال بتنسيق قالب الاستيراد مع الشرح",
                timestamp=datetime.now()
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error logging template export activity: {e}")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in export_template_format: {e}")
        flash("حدث خطأ أثناء تصدير البيانات بتنسيق القالب.", "danger")
        return redirect(url_for("dashboard"))

# إضافة مسارات API لجلب بيانات التصفية الديناميكية
@question_bp.route("/api/filter_options/<field>")
@login_required
def get_filter_options(field):
    """
    جلب خيارات التصفية الديناميكية للمناهج والوحدات والدروس
    """
    try:
        if field == "course":
            courses = Course.query.order_by(Course.name).all()
            options = [{"value": course.name, "text": course.name} for course in courses]
        elif field == "unit":
            course_name = request.args.get("course")
            if course_name:
                units = Unit.query.join(Course).filter(Course.name == course_name).order_by(Unit.name).all()
            else:
                units = Unit.query.order_by(Unit.name).all()
            options = [{"value": unit.name, "text": unit.name} for unit in units]
        elif field == "lesson":
            unit_name = request.args.get("unit")
            course_name = request.args.get("course")
            if unit_name and course_name:
                lessons = Lesson.query.join(Unit).join(Course).filter(
                    Unit.name == unit_name, Course.name == course_name
                ).order_by(Lesson.name).all()
            elif unit_name:
                lessons = Lesson.query.join(Unit).filter(Unit.name == unit_name).order_by(Lesson.name).all()
            else:
                lessons = Lesson.query.order_by(Lesson.name).all()
            options = [{"value": lesson.name, "text": lesson.name} for lesson in lessons]
        else:
            options = []
            
        return jsonify({"success": True, "options": options})
        
    except Exception as e:
        current_app.logger.error(f"Error getting filter options for {field}: {e}")
        return jsonify({"success": False, "error": str(e)})

@question_bp.route("/export/filtered_data", methods=["POST"])
@login_required
def export_filtered_data():
    """
    تصدير البيانات المفلترة مع الحقول المختارة
    """
    try:
        # استقبال البيانات من النموذج
        data_type = request.form.get('data_type', 'all')
        selected_fields = request.form.getlist('fields')
        export_format = request.form.get('format', 'xlsx')
        
        # استقبال التصفيات
        filter_fields = request.form.getlist('filter_field[]')
        filter_operators = request.form.getlist('filter_operator[]')
        filter_values = request.form.getlist('filter_value[]')
        
        # تحضير قائمة التصفيات
        filters = []
        for i in range(len(filter_fields)):
            if i < len(filter_operators) and i < len(filter_values):
                if filter_fields[i] and filter_operators[i] and filter_values[i]:
                    filters.append({
                        'field': filter_fields[i],
                        'operator': filter_operators[i],
                        'value': filter_values[i]
                    })
        
        # التحقق من وجود حقول مختارة
        if not selected_fields:
            flash("يجب اختيار حقل واحد على الأقل للتصدير.", "warning")
            return redirect(url_for("dashboard"))
        
        # تحضير البيانات
        data = prepare_export_data(data_type, selected_fields, filters)
        
        if not data:
            flash("لا توجد بيانات للتصدير بناءً على التصفيات المحددة.", "warning")
            return redirect(url_for("dashboard"))
        
        # إنشاء DataFrame
        df = pd.DataFrame(data)
        
        # تحضير اسم الملف
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"export_{data_type}_{timestamp}"
        
        # إنشاء الملف بناءً على التنسيق المطلوب
        if export_format == 'xlsx':
            filename = f"{filename_base}.xlsx"
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='البيانات')
            output.seek(0)
            
            # تسجيل النشاط
            try:
                activity = Activity(
                    user_id=current_user.id,
                    action="تصدير البيانات",
                    description=f"تم تصدير {len(data)} عنصر من نوع {data_type} بصيغة Excel",
                    timestamp=datetime.now()
                )
                db.session.add(activity)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error logging export activity: {e}")
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
        elif export_format == 'csv':
            filename = f"{filename_base}.csv"
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            
            # تحويل إلى BytesIO
            bytes_output = io.BytesIO()
            bytes_output.write(output.getvalue().encode('utf-8-sig'))
            bytes_output.seek(0)
            
            # تسجيل النشاط
            try:
                activity = Activity(
                    user_id=current_user.id,
                    action="تصدير البيانات",
                    description=f"تم تصدير {len(data)} عنصر من نوع {data_type} بصيغة CSV",
                    timestamp=datetime.now()
                )
                db.session.add(activity)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error logging export activity: {e}")
            
            return send_file(
                bytes_output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
            
        elif export_format == 'pdf':
            # للـ PDF، سنحتاج مكتبة إضافية مثل reportlab
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.lib import colors
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                
                filename = f"{filename_base}.pdf"
                output = io.BytesIO()
                
                # إنشاء مستند PDF
                doc = SimpleDocTemplate(output, pagesize=A4)
                elements = []
                
                # إضافة عنوان
                styles = getSampleStyleSheet()
                title = Paragraph(f"تقرير {data_type}", styles['Title'])
                elements.append(title)
                
                # تحويل البيانات إلى جدول
                table_data = [list(df.columns)]  # العناوين
                for _, row in df.iterrows():
                    table_data.append([str(cell) for cell in row])
                
                # إنشاء الجدول
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                elements.append(table)
                doc.build(elements)
                output.seek(0)
                
                # تسجيل النشاط
                try:
                    activity = Activity(
                        user_id=current_user.id,
                        action="تصدير البيانات",
                        description=f"تم تصدير {len(data)} عنصر من نوع {data_type} بصيغة PDF",
                        timestamp=datetime.now()
                    )
                    db.session.add(activity)
                    db.session.commit()
                except Exception as e:
                    current_app.logger.error(f"Error logging export activity: {e}")
                
                return send_file(
                    output,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
                
            except ImportError:
                flash("مكتبة PDF غير متوفرة. يرجى استخدام Excel أو CSV.", "warning")
                return redirect(url_for("dashboard"))
            except Exception as e:
                current_app.logger.error(f"Error creating PDF: {e}")
                flash("حدث خطأ أثناء إنشاء ملف PDF.", "danger")
                return redirect(url_for("dashboard"))
        
        else:
            flash("تنسيق التصدير غير مدعوم.", "danger")
            return redirect(url_for("dashboard"))
            
    except Exception as e:
        current_app.logger.error(f"Error in export_filtered_data: {e}")
        flash("حدث خطأ أثناء تصدير البيانات.", "danger")
        return redirect(url_for("dashboard"))

# --- get_sorted_lessons function (keep as is) --- #
def get_sorted_lessons():
    try:
        lessons = (
            Lesson.query
            .join(Lesson.unit)
            .join(Unit.course)
            .options(
                contains_eager(Lesson.unit).contains_eager(Unit.course)
            )
            .order_by(Course.name, Unit.name, Lesson.name)
            .all()
        )
        return lessons
    except Exception as e:
        current_app.logger.exception("Error fetching sorted lessons.")
        return []

# --- add_question route (Uses modified save_upload) --- #
@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")

        q_image_path = None
        if q_image_file and q_image_file.filename:
             if not allowed_image_file(q_image_file.filename):
                 flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
             else:
                 # Uses the Cloudinary-compatible save_upload function
                 q_image_path = save_upload(q_image_file, subfolder="questions")
                 if q_image_path is None:
                     flash("فشل رفع صورة السؤال. تحقق من إعدادات Cloudinary والسجلات.", "danger")

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        
        option_keys_check = [key for key in request.form if key.startswith("option_text_")]
        option_files_check = [key for key in request.files if key.startswith("option_image_")]
        if (option_keys_check or option_files_check) and correct_option_index_str is None:
            error_messages.append("يجب تحديد الإجابة الصحيحة.")

        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                     error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        options_data_from_form = []
        max_submitted_index = -1
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            option_image_path = None

            if option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    error_messages.append(f"نوع ملف صورة الخيار رقم {i+1} غير مسموح به.")
                else:
                    # Uses the Cloudinary-compatible save_upload function
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    if option_image_path is None:
                        error_messages.append(f"فشل رفع صورة الخيار رقم {i+1}. تحقق من إعدادات Cloudinary والسجلات.")

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            form_data = request.form.to_dict()
            repop_options = []
            for i in range(max_submitted_index + 1):
                 idx_str = str(i)
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt else None
                 repop_options.append({"option_text": opt_text, "image_url": img_url})
            form_data["options_repop"] = repop_options
            form_data["correct_option_repop"] = correct_option_index_str
            form_data["question_image_url_repop"] = q_image_path
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال", form=form)

        try:
            new_question = Question(
                question_text=question_text if question_text else None,
                lesson_id=lesson_id,
                image_url=q_image_path,
                explanation=request.form.get("explanation", "").strip() or None,
                explanation_image_path=None,
                is_blocked=(request.form.get("is_blocked") == "1")  # معالجة حقل منع السؤال
            )
            db.session.add(new_question)
            db.session.flush()
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            for opt_data in options_data_from_form:
                # --- Logic to set option_text to image_url if option_text is empty and image_url exists ---
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"] # Set option_text to the image_url
                elif not option_text_to_save: # If option_text is still empty (and no image_url or image_url was not used)
                    option_text_to_save = None

                option = Option(
                    option_text=option_text_to_save,
                    image_url=opt_data["image_url"],
                    is_correct=opt_data["is_correct"],
                    question_id=new_question.question_id
                )
                db.session.add(option)
            
            db.session.commit()
            current_app.logger.info("Transaction committed successfully. Question and options saved.")
            flash("تمت إضافة السؤال بنجاح!", "success")
            
            # تسجيل النشاط بعد إضافة السؤال بنجاح
            try:
                # الحصول على معلومات الدرس والوحدة والدورة
                lesson = Lesson.query.get(lesson_id)
                lesson_name = lesson.name if lesson else None
                unit_name = lesson.unit.name if lesson and lesson.unit else None
                course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                
                # تسجيل النشاط
                Activity.log_activity(
                    action_type="create",
                    entity_type="question",
                    entity_id=new_question.question_id,
                    description=f"تمت إضافة سؤال جديد في الدرس: {lesson_name}",
                    lesson_name=lesson_name,
                    unit_name=unit_name,
                    course_name=course_name,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
            except Exception as activity_error:
                current_app.logger.error(f"Error logging activity: {activity_error}")
                # لا نريد أن يؤثر خطأ تسجيل النشاط على تدفق العملية الأساسية
            
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_err:
            db.session.rollback()
            current_app.logger.exception("Database error during question creation.")
            flash("حدث خطأ في قاعدة البيانات أثناء إضافة السؤال.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال", form=form)
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Unexpected error during question creation.")
            flash("حدث خطأ غير متوقع أثناء إضافة السؤال.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال", form=form)

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, submit_text="إضافة سؤال", form=form)

# --- START: Import Questions Route (Modified for Cloudinary) --- #
@question_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_questions():
    """Import questions from Excel or CSV file."""
    current_app.logger.info("Entering import_questions route.")
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()

    if request.method == "POST":
        current_app.logger.info("POST request received for import_questions.")
        
        # Debug logging for request data
        current_app.logger.debug(f"Form data: {request.form}")
        current_app.logger.debug(f"Files: {request.files}")
        
        lesson_id = request.form.get("lesson_id")  # Optional now, as we'll use Course/Unit/Lesson names from Excel
        # lesson_id is now optional - if not provided, we'll use the names from the Excel file
        
        file = request.files.get("question_file")
        if not file or not file.filename:
            flash("الرجاء اختيار ملف للاستيراد.", "danger")
            current_app.logger.warning("No file provided in import form.")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
        
        if not allowed_import_file(file.filename):
            flash("نوع الملف غير مسموح به. يرجى استخدام ملف Excel (.xlsx) أو CSV (.csv).", "danger")
            current_app.logger.warning(f"File type not allowed: {file.filename}")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
        
        # Process the file
        try:
            # Read the file into a pandas DataFrame
            if file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:  # CSV
                df = pd.read_csv(file)
            
            current_app.logger.info(f"File read successfully. Shape: {df.shape}")
            current_app.logger.debug(f"Columns in file: {df.columns.tolist()}")
            
            # Validate columns (Explanation is optional)
            required_columns = [col for col in EXPECTED_IMPORT_COLUMNS if col != "Explanation"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                flash(f"الملف يفتقد إلى الأعمدة التالية: {', '.join(missing_columns)}", "danger")
                current_app.logger.warning(f"Missing columns in import file: {missing_columns}")
                return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
            
            # Process each row
            imported_count = 0
            error_details = []
            
            for index, row in df.iterrows():
                try:
                    # Extract course, unit, and lesson names
                    course_name = row["Course Name"] if pd.notna(row.get("Course Name")) else None
                    unit_name = row["Unit Name"] if pd.notna(row.get("Unit Name")) else None
                    lesson_name = row["Lesson Name"] if pd.notna(row.get("Lesson Name")) else None
                    
                    # Validate course, unit, and lesson names
                    if not course_name or not unit_name or not lesson_name:
                        error_details.append(f"صف {index+2}: يجب توفير اسم المنهج والوحدة والدرس.")
                        continue
                    
                    # Find the lesson by course, unit, and lesson names
                    lesson = Lesson.query.join(Unit).join(Course).filter(
                        Course.name == course_name,
                        Unit.name == unit_name,
                        Lesson.name == lesson_name
                    ).first()
                    
                    if not lesson:
                        error_details.append(f"صف {index+2}: لم يتم العثور على الدرس '{lesson_name}' في الوحدة '{unit_name}' في المنهج '{course_name}'.")
                        continue
                    
                    current_lesson_id = lesson.id
                    
                    # Extract question data
                    question_text = row["Question Text"] if pd.notna(row["Question Text"]) else None
                    question_image_url = row["Question Image URL"] if pd.notna(row["Question Image URL"]) else None
                    
                    # Skip row if both question text and image are missing
                    if not question_text and not question_image_url:
                        error_details.append(f"صف {index+2}: يجب توفير نص السؤال أو صورة له.")
                        continue
                    
                    # Extract options data
                    options_data = []
                    valid_options_count = 0
                    correct_option_number = None
                    
                    if pd.notna(row["Correct Option Number"]):
                        try:
                            correct_option_number = int(row["Correct Option Number"])
                            if correct_option_number < 1 or correct_option_number > 4:
                                error_details.append(f"صف {index+2}: رقم الإجابة الصحيحة يجب أن يكون بين 1 و 4.")
                                continue
                        except (ValueError, TypeError):
                            error_details.append(f"صف {index+2}: رقم الإجابة الصحيحة يجب أن يكون رقمًا صحيحًا.")
                            continue
                    else:
                        error_details.append(f"صف {index+2}: يجب تحديد رقم الإجابة الصحيحة.")
                        continue
                    
                    for i in range(1, 5):
                        option_text = row[f"Option {i} Text"] if pd.notna(row[f"Option {i} Text"]) else None
                        option_image_url = row[f"Option {i} Image URL"] if pd.notna(row[f"Option {i} Image URL"]) else None
                        
                        if option_text or option_image_url:
                            valid_options_count += 1
                            options_data.append({
                                "option_text": option_text,
                                "image_url": option_image_url,
                                "is_correct": (i == correct_option_number)
                            })
                    
                    if valid_options_count < 2:
                        error_details.append(f"صف {index+2}: يجب توفير خيارين صالحين على الأقل.")
                        continue
                    
                    if correct_option_number > valid_options_count:
                        error_details.append(f"صف {index+2}: رقم الإجابة الصحيحة يشير إلى خيار غير موجود.")
                        continue
                    
                    # Extract explanation if available
                    explanation = row["Explanation"] if pd.notna(row.get("Explanation")) else None
                    
                    # Create question
                    new_question = Question(
                        question_text=question_text,
                        lesson_id=current_lesson_id,
                        image_url=question_image_url,
                        explanation=explanation
                    )
                    db.session.add(new_question)
                    db.session.flush()  # Get the question ID
                    
                    # Create options
                    for opt_data in options_data:
                        option = Option(
                            option_text=opt_data["option_text"],
                            image_url=opt_data["image_url"],
                            is_correct=opt_data["is_correct"],
                            question_id=new_question.question_id
                        )
                        db.session.add(option)
                    
                    imported_count += 1
                    
                except Exception as row_error:
                    error_details.append(f"صف {index+2}: {str(row_error)}")
                    current_app.logger.exception(f"Error processing row {index+2}: {row_error}")
            
            # Commit all changes if there were any successful imports
            if imported_count > 0:
                db.session.commit()
                current_app.logger.info(f"Successfully imported {imported_count} questions.")
                flash(f"تم استيراد {imported_count} سؤال بنجاح!", "success")
                
                # تسجيل النشاط بعد استيراد الأسئلة بنجاح
                try:
                    # الحصول على معلومات الدرس والوحدة والدورة
                    lesson = Lesson.query.get(lesson_id)
                    lesson_name = lesson.name if lesson else None
                    unit_name = lesson.unit.name if lesson and lesson.unit else None
                    course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                    
                    # تسجيل النشاط
                    Activity.log_activity(
                        action_type="import",
                        entity_type="question",
                        entity_id=None,  # لا يوجد معرف محدد لأننا استوردنا عدة أسئلة
                        description=f"تم استيراد {imported_count} سؤال إلى الدرس: {lesson_name}",
                        lesson_name=lesson_name,
                        unit_name=unit_name,
                        course_name=course_name,
                        user_id=current_user.id if current_user.is_authenticated else None
                    )
                except Exception as activity_error:
                    current_app.logger.error(f"Error logging activity: {activity_error}")
                    # لا نريد أن يؤثر خطأ تسجيل النشاط على تدفق العملية الأساسية
            
            # Show errors if any
            if error_details:
                error_summary = f"تم استيراد {imported_count} سؤال، مع {len(error_details)} أخطاء:"
                for i, error in enumerate(error_details[:5]):  # Show first 5 errors
                    flash(error, "warning")
                if len(error_details) > 5:
                    flash(f"... و {len(error_details) - 5} أخطاء أخرى.", "warning")
                
                flash(error_summary, "danger")
                current_app.logger.error(f"Import errors occurred: {error_details}")
                return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
            else:
                if imported_count > 0:
                     return redirect(url_for("question.list_questions"))
                else:
                     flash("لم يتم العثور على أسئلة صالحة للاستيراد في الملف.", "warning")
                     return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)

        except Exception as e:
            current_app.logger.exception(f"Error processing import file: {e}")
            flash(f"حدث خطأ أثناء معالجة ملف الاستيراد: {str(e)}", "danger")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
    
    # GET request - show the form
    return render_template("question/import_questions.html", lessons=lessons, form=form)

# --- download_import_template route (keep as is) --- #
@question_bp.route("/import/template")
@login_required
def download_import_template():
    try:
        # Create a sample DataFrame with the expected columns
        df = pd.DataFrame(columns=EXPECTED_IMPORT_COLUMNS)
        
        # Add a sample row
        sample_row = {
            "Course Name": "مثال: كيمياء 1",
            "Unit Name": "مثال: الوحدة الأولى",
            "Lesson Name": "مثال: الدرس الأول",
            "Question Text": "ما هي الصيغة الكيميائية للماء؟",
            "Question Image URL": "",
            "Option 1 Text": "H₂O",
            "Option 1 Image URL": "",
            "Option 2 Text": "CO₂",
            "Option 2 Image URL": "",
            "Option 3 Text": "NaCl",
            "Option 3 Image URL": "",
            "Option 4 Text": "O₂",
            "Option 4 Image URL": "",
            "Correct Option Number": 1,
            "Explanation": "الماء يتكون من ذرتين من الهيدروجين وذرة واحدة من الأكسجين"
        }
        df = pd.concat([df, pd.DataFrame([sample_row])], ignore_index=True)
        
        # Create a BytesIO object to store the Excel file
        output = io.BytesIO()
        
        # Write the DataFrame to the BytesIO object
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Questions')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Questions']
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                # Convert to Excel column width which is based on the width of '0' character
                worksheet.column_dimensions[chr(65 + i)].width = max_width
        
        # Seek to the beginning of the BytesIO object
        output.seek(0)
        
        # Send the file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='question_import_template.xlsx'
        )
        
    except Exception as e:
        current_app.logger.exception("Error generating import template")
        flash("حدث خطأ أثناء إنشاء قالب الاستيراد.", "danger")
        return redirect(url_for("question.import_questions"))

# --- edit_question route (Uses modified save_upload) --- #
@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    lessons = get_sorted_lessons()
    
    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        delete_question_image = request.form.get("delete_question_image") == "1"
        explanation = request.form.get("explanation", "").strip()

        q_image_path = question.image_url
        if delete_question_image:
            q_image_path = None
        elif q_image_file and q_image_file.filename:
            if not allowed_image_file(q_image_file.filename):
                flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
            else:
                # Uses the Cloudinary-compatible save_upload function
                new_q_image_path = save_upload(q_image_file, subfolder="questions")
                if new_q_image_path is None:
                    flash("فشل رفع صورة السؤال. تحقق من إعدادات Cloudinary والسجلات.", "danger")
                else:
                    q_image_path = new_q_image_path

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        
        option_keys_check = [key for key in request.form if key.startswith("option_text_")]
        option_files_check = [key for key in request.files if key.startswith("option_image_")]
        if (option_keys_check or option_files_check) and correct_option_index_str is None:
            error_messages.append("يجب تحديد الإجابة الصحيحة.")

        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                     error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        options_data_from_form = []
        max_submitted_index = -1
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            delete_option_image = request.form.get(f"delete_option_image_{index_str}") == "1"
            option_id = request.form.get(f"option_id_{index_str}")
            
            # Find existing option if we have an option_id
            existing_option = None
            if option_id:
                try:
                    option_id = int(option_id)
                    existing_option = next((opt for opt in question.options if opt.option_id == option_id), None)
                except ValueError:
                    pass
            
            option_image_path = existing_option.image_url if existing_option else None
            
            if delete_option_image:
                option_image_path = None
            elif option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    error_messages.append(f"نوع ملف صورة الخيار رقم {i+1} غير مسموح به.")
                else:
                    # Uses the Cloudinary-compatible save_upload function
                    new_option_image_path = save_upload(option_image_file, subfolder="options")
                    if new_option_image_path is None:
                        error_messages.append(f"فشل رفع صورة الخيار رقم {i+1}. تحقق من إعدادات Cloudinary والسجلات.")
                    else:
                        option_image_path = new_option_image_path

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_id": option_id,
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            form_data = request.form.to_dict()
            repop_options = []
            for i in range(max_submitted_index + 1):
                 idx_str = str(i)
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 opt_id = request.form.get(f"option_id_{idx_str}")
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt else None
                 repop_options.append({"option_id": opt_id, "option_text": opt_text, "image_url": img_url})
            form_data["options_repop"] = repop_options
            form_data["correct_option_repop"] = correct_option_index_str
            form_data["question_image_url_repop"] = q_image_path
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=form_data, submit_text="تحديث السؤال", form=form)

        try:
            # Update question
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path
            question.explanation = explanation or None
            question.is_blocked = (request.form.get("is_blocked") == "1")  # معالجة حقل منع السؤال
            
            # Track existing options to determine which to delete
            existing_option_ids = {opt.option_id for opt in question.options}
            updated_option_ids = set()
            
            # Update or create options
            for opt_data in options_data_from_form:
                option_id = opt_data.get("option_id")
                
                # --- Logic to set option_text to image_url if option_text is empty and image_url exists ---
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"] # Set option_text to the image_url
                elif not option_text_to_save: # If option_text is still empty (and no image_url or image_url was not used)
                    option_text_to_save = None
                
                if option_id:
                    # Update existing option
                    try:
                        option_id = int(option_id)
                        option = next((opt for opt in question.options if opt.option_id == option_id), None)
                        if option:
                            option.option_text = option_text_to_save
                            option.image_url = opt_data["image_url"]
                            option.is_correct = opt_data["is_correct"]
                            updated_option_ids.add(option_id)
                    except (ValueError, TypeError):
                        # If option_id is not a valid integer, create a new option
                        option = Option(
                            option_text=option_text_to_save,
                            image_url=opt_data["image_url"],
                            is_correct=opt_data["is_correct"],
                            question_id=question.question_id
                        )
                        db.session.add(option)
                else:
                    # Create new option
                    option = Option(
                        option_text=option_text_to_save,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(option)
            
            # Delete options that were not updated or created
            options_to_delete = existing_option_ids - updated_option_ids
            if options_to_delete:
                Option.query.filter(Option.option_id.in_(options_to_delete)).delete(synchronize_session=False)
            
            db.session.commit()
            current_app.logger.info(f"Question ID {question_id} updated successfully.")
            flash("تم تحديث السؤال بنجاح!", "success")
            
            # تسجيل النشاط بعد تعديل السؤال بنجاح
            try:
                # الحصول على معلومات الدرس والوحدة والدورة
                lesson = Lesson.query.get(lesson_id)
                lesson_name = lesson.name if lesson else None
                unit_name = lesson.unit.name if lesson and lesson.unit else None
                course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                
                # تسجيل النشاط
                Activity.log_activity(
                    action_type="update",
                    entity_type="question",
                    entity_id=question.question_id,
                    description=f"تم تعديل سؤال في الدرس: {lesson_name}",
                    lesson_name=lesson_name,
                    unit_name=unit_name,
                    course_name=course_name,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
            except Exception as activity_error:
                current_app.logger.error(f"Error logging activity: {activity_error}")
                # لا نريد أن يؤثر خطأ تسجيل النشاط على تدفق العملية الأساسية
            
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_err:
            db.session.rollback()
            current_app.logger.exception(f"Database error during question update for ID {question_id}.")
            flash("حدث خطأ في قاعدة البيانات أثناء تحديث السؤال.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="تحديث السؤال", form=form)
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Unexpected error during question update for ID {question_id}.")
            flash("حدث خطأ غير متوقع أثناء تحديث السؤال.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="تحديث السؤال", form=form)

    # GET request - show the form with existing data
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="تحديث السؤال", form=form)

# --- delete_question route (keep as is) --- #
@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    
    try:
        # Get lesson info before deleting for activity logging
        lesson_id = question.lesson_id
        lesson = Lesson.query.get(lesson_id) if lesson_id else None
        lesson_name = lesson.name if lesson else None
        unit_name = lesson.unit.name if lesson and lesson.unit else None
        course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
        
        # Delete associated options first (should happen automatically with cascade, but being explicit)
        Option.query.filter_by(question_id=question_id).delete()
        
        # Delete the question
        db.session.delete(question)
        db.session.commit()
        
        flash("تم حذف السؤال بنجاح!", "success")
        
        # تسجيل النشاط بعد حذف السؤال بنجاح
        try:
            # تسجيل النشاط
            Activity.log_activity(
                action_type="delete",
                entity_type="question",
                entity_id=question_id,
                description=f"تم حذف سؤال من الدرس: {lesson_name}",
                lesson_name=lesson_name,
                unit_name=unit_name,
                course_name=course_name,
                user_id=current_user.id if current_user.is_authenticated else None
            )
        except Exception as activity_error:
            current_app.logger.error(f"Error logging activity: {activity_error}")
            # لا نريد أن يؤثر خطأ تسجيل النشاط على تدفق العملية الأساسية
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}.")
        flash("حدث خطأ أثناء محاولة حذف السؤال.", "danger")
    
    return redirect(url_for("question.list_questions"))


# ===== Route لصفحة الاختبار التفاعلي =====
@question_bp.route('/quiz')
@login_required
def quiz():
    """
    صفحة الاختبار التفاعلي
    """
    return render_template('quiz.html')


# ===== Route لصفحة استخراج وتوليد نماذج الاختبار =====
@question_bp.route('/export-exam')
@login_required
def export_exam():
    """
    صفحة استخراج وتوليد نماذج الاختبار
    """
    return render_template('question/export_exam.html')


@question_bp.route('/download-exam-word', methods=['POST'])
@login_required
def download_exam_word():
    """
    تحميل نموذج الاختبار كملف Word
    
    Request JSON:
    {
        "question_ids": [1, 2, 3, ...],
        "include_answers": true/false,
        "exam_title": "عنوان الاختبار",
        "course_name": "اسم المنهج",
        "unit_name": "اسم الوحدة",
        "lesson_name": "اسم الدرس"
    }
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from exam_generator import generate_exam
        from models.exam_header_settings import ExamHeaderSettings
        
        data = request.get_json()
        question_ids = data.get("question_ids", [])
        include_answers = data.get("include_answers", False)
        exam_title = data.get("exam_title", "نموذج الاختبار")
        course_name = data.get("course_name", "")
        unit_name = data.get("unit_name", "")
        lesson_name = data.get("lesson_name", "")
        output_format = data.get("output_format", "word").lower()  # أضفنا هذا
        
        # استخراج الإعدادات المحفوظة
        header_settings = ExamHeaderSettings.query.first()
        if header_settings:
            country = header_settings.country or ""
            ministry = header_settings.ministry or ""
            education_department = header_settings.education_department or ""
            school_name = header_settings.school_name or ""
            subject = header_settings.subject or ""
            exam_time = header_settings.time or ""
            grade = header_settings.grade or ""
            total_score = header_settings.total_score or 30
            checker_name = header_settings.checker_name or ""
            reviewer_name = header_settings.reviewer_name or ""
            exam_date = header_settings.exam_date or ""
        else:
            # قيم افتراضية
            country = "المملكة العربية السعودية"
            ministry = "وزارة التعليم"
            education_department = "الإدارة العامة للتعليم"
            school_name = ""
            subject = ""
            exam_time = ""
            grade = ""
            total_score = 30
            checker_name = ""
            reviewer_name = ""
            exam_date = ""
        
        if not question_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد أسئلة'
            }), 400
        
        # الحصول على الأسئلة من قاعدة البيانات
        questions = Question.query.filter(
            Question.question_id.in_(question_ids)
        ).all()
        
        if not questions:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على الأسئلة المحددة'
            }), 404
        
        # تنسيق الأسئلة مع تنسيق النص للطباعة
        formatted_questions = []
        for question in questions:
            formatted_q = {
                'question_id': question.question_id,
                'question_text': format_text_for_print(question.question_text),
                'options': [
                    {
                        'option_id': opt.option_id,
                        'option_text': format_text_for_print(opt.option_text),
                        'is_correct': opt.is_correct
                    }
                    for opt in sorted(question.options, key=lambda o: o.option_id)
                ],
                'correct_option_id': next(
                    (opt.option_id for opt in question.options if opt.is_correct),
                    None
                )
            }
            formatted_questions.append(formatted_q)
        
        # توليد ملف Word أو PDF باستخدام النظام الموحد
        file_bytes = generate_exam(
            formatted_questions,
            exam_title=exam_title,
            output_format=output_format,  # استخدم الصيغة المطلوبة
            show_answers=include_answers,
            country=country,
            ministry=ministry,
            education_department=education_department,
            school_name=school_name,
            subject=subject,
            time=exam_time,
            grade=grade,
            total_score=total_score,
            checker_name=checker_name,
            reviewer_name=reviewer_name,
            exam_date=exam_date
        )
        
        # إرسال الملف بالصيغة الصحيحة
        if output_format == 'pdf':
            return send_file(
                io.BytesIO(file_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"exam_{int(time.time())}.pdf"
            )
        else:  # word
            return send_file(
                io.BytesIO(file_bytes),
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=f"exam_{int(time.time())}.docx"
            )
        
    except ImportError as ie:
        current_app.logger.error(f"Import error: {ie}")
        return jsonify({
            'success': False,
            'error': 'وحدة توليد الاختبارات غير متاحة'
        }), 500
    except Exception as e:
        current_app.logger.exception(f"Error downloading exam word: {e}")
        return jsonify({
            'success': False,
            'error': f'خطأ في توليد الملف: {str(e)}'
        }), 500


@question_bp.route('/header-settings')
@login_required
def header_settings():
    """عرض صفحة إعدادات الكليشة"""
    return render_template('question/exam_header_settings.html')


@question_bp.route('/save-header-settings', methods=['POST'])
@login_required
def save_header_settings():
    """حفظ إعدادات الكليشة في قاعدة البيانات"""
    try:
        data = request.get_json()
        
        # البحث عن الإعدادات الموجودة أو إنشاء جديدة
        settings = ExamHeaderSettings.query.first()
        if not settings:
            settings = ExamHeaderSettings()
        
        # تحديث البيانات
        settings.country = data.get('country', 'المملكة العربية السعودية')
        settings.ministry = data.get('ministry', 'وزارة التعليم')
        settings.education_department = data.get('education_department', 'الإدارة العامة للتعليم بالمنطقة الشرقية')
        settings.school_name = data.get('school_name', 'مدرسة عبدالرحمن بن القاسم الثانوية')
        settings.subject = data.get('subject', 'كيمياء 4')
        settings.time = data.get('time', 'ثلاث ساعات')
        settings.grade = data.get('grade', 'ثالث ثانوي')
        settings.total_score = data.get('total_score', 30)
        settings.checker_name = data.get('checker_name', '')
        settings.reviewer_name = data.get('reviewer_name', '')
        settings.exam_date = data.get('exam_date', '')
        
        db.session.add(settings)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ الإعدادات بنجاح'
        }), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error saving header settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@question_bp.route('/get-header-settings', methods=['GET'])
@login_required
def get_header_settings():
    """الحصول على إعدادات الكليشة المحفوظة"""
    try:
        settings = ExamHeaderSettings.query.first()
        
        if settings:
            return jsonify({
                'success': True,
                'settings': {
                    'country': settings.country,
                    'ministry': settings.ministry,
                    'education_department': settings.education_department,
                    'school_name': settings.school_name,
                    'subject': settings.subject,
                    'time': settings.time,
                    'grade': settings.grade,
                    'total_score': settings.total_score,
                    'checker_name': settings.checker_name,
                    'reviewer_name': settings.reviewer_name,
                    'exam_date': settings.exam_date
                }
            }), 200
        else:
            return jsonify({
                'success': True,
                'settings': None
            }), 200
            
    except Exception as e:
        current_app.logger.exception(f"Error getting header settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@question_bp.route('/export-exam-pdf', methods=['POST'])
@login_required
def export_exam_pdf():
    """استخراج ملف PDF للاختبار مع جلب البيانات بشكل صحيح"""
    try:
        # محاولة استيراد المولد
        try:
            from src.routes.exam_generator import ExamGenerator
        except ImportError:
            from exam_generator import ExamGenerator
            
        # محاولة استيراد نموذج الإعدادات من المسار الصحيح (كما في دالة الوورد)
        try:
            from src.models.exam_header_settings import ExamHeaderSettings as SettingsModel
        except ImportError:
            try:
                from models.exam_header_settings import ExamHeaderSettings as SettingsModel
            except ImportError:
                # في حال الفشل نستخدم الكلاس المعرف محلياً
                SettingsModel = ExamHeaderSettings
        
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        include_answers = data.get('include_answers', False)
        exam_title = data.get('exam_title', 'نموذج الاختبار')
        
        # جلب الأسئلة
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لا توجد أسئلة محددة'}), 400
        
        # تحويل الأسئلة مع تنسيق النص للطباعة
        questions_data = []
        for q in questions:
            q_dict = {
                'id': q.question_id, 
                'question_text': format_text_for_print(q.question_text), 
                'points': 1, 
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_text': format_text_for_print(opt.option_text), 
                    'is_correct': opt.is_correct
                })
            questions_data.append(q_dict)
        
        # جلب الإعدادات من قاعدة البيانات
        # نستخدم SettingsModel الذي تم استيراده لضمان التطابق مع دالة الوورد
        header_settings = db.session.query(SettingsModel).first()
        
        settings_dict = {}
        if header_settings:
            # استخدام or "" لضمان عدم تمرير None
            settings_dict = {
                'country': header_settings.country or "المملكة العربية السعودية",
                'ministry': header_settings.ministry or "وزارة التعليم",
                'education_department': header_settings.education_department or "",
                'school_name': header_settings.school_name or "",
                'subject': header_settings.subject or "",
                'time': header_settings.time or "",
                'grade': header_settings.grade or "",
                'total_score': header_settings.total_score or 30,
                'checker_name': header_settings.checker_name or "",
                'reviewer_name': header_settings.reviewer_name or "",
                'exam_date': header_settings.exam_date or ""
            }
        
        # تمرير الإعدادات إلى المنشئ وإلى دالة التوليد
        generator = ExamGenerator(header_settings=settings_dict)
        
        pdf_bytes = generator.generate_pdf(
            questions_data, 
            exam_title, 
            include_answers,
            **settings_dict  # فك القاموس تمريره كـ kwargs
        )
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"exam_{int(time.time())}.pdf"
        )
        
    except Exception as e:
        current_app.logger.exception(f"Error exporting PDF: {e}")
        return jsonify({'error': str(e)}), 500
@question_bp.route('/preview-exam-paper', methods=['POST'])
@login_required
def preview_exam_paper():
    """عرض معاينة الاختبار في المتصفح باستخدام نفس القالب الموحد"""
    try:
        # استيراد المولد فقط (لأنه غير موجود في هذا الملف)
        try:
            from src.routes.exam_generator import ExamGenerator
        except ImportError:
            from exam_generator import ExamGenerator
            
        # ملاحظة: لا نقم باستيراد ExamHeaderSettings هنا 
        # لأننا سنستخدم الكلاس المعرف في السطر 48 من هذا الملف مباشرة.

        # استقبال البيانات من الفورم
        question_ids_str = request.form.get('question_ids', '')
        if not question_ids_str:
             return "لا توجد أسئلة محددة", 400
             
        question_ids = [int(x) for x in question_ids_str.split(',')]
        include_answers = request.form.get('include_answers') == 'true'
        
        # ... (باقي الكود كما هو تماماً) ...
        
        questions = get_ordered_questions(question_ids)
        
        # تحويل الأسئلة مع تنسيق النص للطباعة
        questions_data = []
        for q in questions:
            q_dict = {
                'id': q.question_id, 
                'question_text': format_text_for_print(q.question_text), 
                'points': 1, 
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_text': format_text_for_print(opt.option_text), 
                    'is_correct': opt.is_correct, 
                    'option_id': opt.option_id
                })
            q_dict['correct_option_id'] = next((o.option_id for o in q.options if o.is_correct), None)
            questions_data.append(q_dict)

        header_settings = ExamHeaderSettings.query.first()
        settings_dict = {
            'country': header_settings.country or "المملكة العربية السعودية",
            'ministry': header_settings.ministry or "وزارة التعليم",
            'education_department': header_settings.education_department or "",
            'school_name': header_settings.school_name or "",
            'subject': header_settings.subject or "",
            'time': header_settings.time or "",
            'grade': header_settings.grade or "",
            'total_score': header_settings.total_score or 30,
            'checker_name': header_settings.checker_name or "",
            'reviewer_name': header_settings.reviewer_name or "",
            'exam_date': header_settings.exam_date or ""
        }
        
        generator = ExamGenerator(header_settings=settings_dict)
        # توليد HTML فقط للعرض في المتصفح
        html_content = generator.generate_html(questions_data, "نموذج الاختبار", include_answers, **settings_dict)
        
        return html_content
        
    except Exception as e:
        return f"Error: {str(e)}", 500


# ============================================================
# كود توليد النماذج المتعددة مع الباركود
# ============================================================

def generate_qr_code(data_dict):
    """
    توليد باركود QR يحتوي على معلومات الاختبار
    
    Args:
        data_dict: قاموس يحتوي على معلومات الاختبار
        
    Returns:
        Base64 string للصورة
    """
    # تحويل البيانات لنص
    qr_text = f"""المادة: {data_dict.get('subject', '')}
النموذج: {data_dict.get('model', '')}
عدد الأسئلة: {data_dict.get('questions_count', '')}
التاريخ: {data_dict.get('date', '')}""".strip()
    
    # إنشاء الباركود
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=3,
        border=2,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # تحويل لـ Base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{img_base64}"


def shuffle_exam(questions, shuffle_questions=True, shuffle_options=True, seed=None, saved_options_order=None):
    """
    خلط ترتيب الأسئلة والخيارات
    
    Args:
        questions: قائمة الأسئلة
        shuffle_questions: خلط ترتيب الأسئلة
        shuffle_options: خلط ترتيب الخيارات
        seed: بذرة للعشوائية (لإعادة الإنتاج)
        saved_options_order: ترتيب الخيارات المحفوظ لكل سؤال (dict: question_id -> [option_ids])
        
    Returns:
        قائمة الأسئلة المخلوطة مع تتبع الإجابات الصحيحة
    """
    if seed is not None:
        random.seed(seed)
    
    # نسخة عميقة لتجنب تعديل الأصل
    shuffled = copy.deepcopy(questions)
    
    # خلط ترتيب الأسئلة
    if shuffle_questions:
        random.shuffle(shuffled)
    
    # تحويل مفاتيح saved_options_order لـ strings للمقارنة
    saved_order_normalized = {}
    if saved_options_order:
        for k, v in saved_options_order.items():
            saved_order_normalized[str(k)] = [str(x) for x in v]
    
    # خلط ترتيب الخيارات لكل سؤال
    letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
    
    for question in shuffled:
        options = question.get('options', [])
        if not options:
            continue
            
        question_id = str(question.get('question_id', ''))
        
        # التحقق من وجود ترتيب محفوظ لهذا السؤال
        if saved_order_normalized and question_id in saved_order_normalized:
            saved_order = saved_order_normalized[question_id]
            # إنشاء قاموس للخيارات حسب الـ ID
            options_by_id = {str(opt.get('option_id', '')): opt for opt in options}
            
            # ترتيب الخيارات حسب الترتيب المحفوظ
            ordered_options = []
            for opt_id in saved_order:
                if opt_id in options_by_id:
                    ordered_options.append(options_by_id[opt_id])
            
            # إذا تم ترتيب جميع الخيارات بنجاح، نستخدم الترتيب المحفوظ
            if len(ordered_options) == len(options):
                options = ordered_options
            elif shuffle_options:
                # إذا فشل الترتيب المحفوظ، نخلط عشوائياً
                random.shuffle(options)
        elif shuffle_options:
            # لا يوجد ترتيب محفوظ، نخلط عشوائياً
            random.shuffle(options)
        
        # تحديث الإجابة الصحيحة بعد الترتيب
        for i, opt in enumerate(options):
            if opt.get('is_correct'):
                question['correct_answer_index'] = i
                question['correct_answer_letter'] = letters[i] if i < len(letters) else str(i+1)
                break
        
        question['options'] = options
    
    return shuffled


@question_bp.route('/generate-multi-models', methods=['POST'])
@login_required
def generate_multi_models():
    """
    توليد نماذج متعددة من الاختبار بترتيب مختلف + باركود
    """
    try:
        # استيراد WeasyPrint
        from weasyprint import HTML as WeasyHTML
        
        data = request.get_json()
        current_app.logger.info(f"Received data for multi-models: {data}")
        
        question_ids = data.get('question_ids', [])
        models = data.get('models', ['أ'])  # النماذج المطلوبة
        include_answers = data.get('include_answers', False)
        include_answer_sheet = data.get('include_answer_sheet', False)
        include_barcode = data.get('include_barcode', True)
        shuffle_options = data.get('shuffle_options', True)
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد أسئلة'}), 400
        
        current_app.logger.info(f"Processing {len(question_ids)} questions for models: {models}")
        
        # جلب الأسئلة من قاعدة البيانات
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        current_app.logger.info(f"Found {len(questions)} questions in database")
        
        # تحويل الأسئلة لقاموس مع تنسيق النص للطباعة
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': format_text_for_print(q.question_text or ''),
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': format_text_for_print(getattr(opt, 'option_text', '') or ''),
                    'image_url': getattr(opt, 'image_url', None) or '',
                    'is_correct': getattr(opt, 'is_correct', False)
                })
            questions_data.append(q_dict)
        
        current_app.logger.info(f"Converted {len(questions_data)} questions to dict")
        
        # جلب إعدادات الهيدر
        settings = ExamHeaderSettings.query.first()
        header_settings = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'time': settings.time if settings else '',
            'grade': settings.grade if settings else '',
            'total_score': settings.total_score if settings else 30,
            'checker_name': settings.checker_name if settings else '',
            'reviewer_name': settings.reviewer_name if settings else ''
        }
        
        # تحويل الشعار لـ base64 لتجنب مشاكل WeasyPrint مع timeout
        logo_base64 = None
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode('utf-8')}"
        except Exception as logo_err:
            current_app.logger.warning(f"Could not load logo: {logo_err}")
        
        header_settings['logo_base64'] = logo_base64
        header_settings['logo_url'] = url_for('static', filename='images/logo.png', _external=True)
        
        # توليد HTML لكل نموذج
        all_models_html = []
        answer_keys = {}  # مفاتيح الإجابات لكل نموذج
        
        for i, model_letter in enumerate(models):
            # 🔧 seed يعتمد على: محتوى الأسئلة + النموذج + أرقام أولية ضخمة متباعدة
            # استخدام أرقام أولية ضخمة جداً لضمان اختلاف كبير بين النماذج
            question_ids_str = ''.join(str(q['question_id']) for q in questions_data)
            random_offset = [15485863, 32452843, 49979687, 67867967][i % 4]  # أرقام أولية ضخمة
            seed = (hash(question_ids_str + model_letter) + i * 7919 + random_offset) % (2**31)
            shuffled_questions = shuffle_exam(
                questions_data, 
                shuffle_questions=True, 
                shuffle_options=shuffle_options,
                seed=seed
            )
            
            # حفظ مفتاح الإجابات
            letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
            answer_keys[model_letter] = []
            for j, q in enumerate(shuffled_questions):
                correct_letter = q.get('correct_answer_letter', '')
                if not correct_letter:
                    # البحث عن الإجابة الصحيحة
                    for k, opt in enumerate(q['options']):
                        if opt.get('is_correct'):
                            correct_letter = letters[k] if k < len(letters) else str(k+1)
                            break
                answer_keys[model_letter].append({
                    'question_num': j + 1,
                    'answer': correct_letter
                })
            
            # توليد الباركود
            qr_code_data = None
            if include_barcode:
                qr_code_data = generate_qr_code({
                    'subject': header_settings['subject'],
                    'model': model_letter,
                    'questions_count': len(shuffled_questions),
                    'date': datetime.now().strftime('%Y-%m-%d')
                })
            
            # توليد HTML للنموذج
            model_html = render_template(
                'question/exam_paper_layout_with_barcode.html',
                questions=shuffled_questions,
                model_letter=model_letter,
                qr_code=qr_code_data,
                show_answers=include_answers,
                exam_title=f"نموذج الاختبار - {model_letter}",
                **header_settings
            )
            
            all_models_html.append(model_html)
        
        # إضافة بطاقة التصحيح إذا مطلوبة
        if include_answer_sheet:
            answer_sheet_html = render_template(
                'question/answer_sheet_template.html',
                answer_keys=answer_keys,
                models=models,
                questions_count=len(questions_data),
                **header_settings
            )
            all_models_html.append(answer_sheet_html)
        
        # دمج كل النماذج في HTML واحد - مبسط للأداء
        combined_html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 15mm; }
.page-break { page-break-after: always; }
body { font-family: Arial, Tahoma, sans-serif; font-size: 12px; }
</style>
</head>
<body>
"""
        
        for i, model_html in enumerate(all_models_html):
            combined_html += model_html
            if i < len(all_models_html) - 1:
                combined_html += '<div class="page-break"></div>'
        
        combined_html += "</body></html>"
        
        current_app.logger.info(f"Combined HTML length: {len(combined_html)} chars")
        
        # تحويل لـ PDF مع timeout handling
        pdf_buffer = io.BytesIO()
        try:
            # استخدام base_url محلي لتجنب HTTP requests
            WeasyHTML(string=combined_html, base_url='/').write_pdf(pdf_buffer)
        except Exception as pdf_err:
            current_app.logger.error(f"WeasyPrint PDF generation failed: {pdf_err}")
            # Fallback: إرجاع HTML بدلاً من PDF
            return combined_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'exam_models_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        
    except Exception as e:
        current_app.logger.exception(f"Error generating multi models: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/preview-multi-models', methods=['POST'])
@login_required
def preview_multi_models():
    """
    معاينة النماذج المتعددة كـ HTML في المتصفح (للطباعة)
    هذا يتجنب مشاكل WeasyPrint timeout وتم تحديثه لضمان اختلاف الإجابات بين النماذج
    """
    try:
        data = request.get_json()
        
        question_ids = data.get('question_ids', [])
        models = data.get('models', ['أ'])
        include_answers = data.get('include_answers', False)
        include_answer_sheet = data.get('include_answer_sheet', False)
        include_barcode = data.get('include_barcode', True)
        font_size = data.get('font_size', 14)  # حجم الخط الافتراضي 14px
        image_size = data.get('image_size', 100)  # حجم الصور الافتراضي 100%
        
        # ترتيب الخيارات المحفوظ (من اختبار محفوظ سابقاً)
        saved_options_order = data.get('saved_options_order', {})
        
        # إعدادات التنسيق المتقدمة
        columns = data.get('columns', 2)  # عدد الأعمدة الافتراضي 2
        spacing = data.get('spacing', 'normal')  # المسافة الافتراضية متوسطة
        options_layout = data.get('options_layout', 'vertical')  # تنسيق الخيارات الافتراضي عمودي
        
        # إعدادات تنسيق الكليشة
        header_format = {
            'header_size': data.get('header_size', 'medium'),
            'show_logo': data.get('show_logo', True),
            'logo_size': data.get('logo_size', 'medium'),
            'qr_size': data.get('qr_size', 'medium'),
            'show_grades_table': data.get('show_grades_table', True),
            'show_extra_grade_field': data.get('show_extra_grade_field', False),
            'show_student_name': data.get('show_student_name', True),
            'show_student_class': data.get('show_student_class', True),
            'show_student_seat_no': data.get('show_student_seat_no', True),
            'show_student_signature': data.get('show_student_signature', False),
            'name_line_length': data.get('name_line_length', 'medium'),
            'exam_type': data.get('exam_type', 'نهاية'),
            'semester': data.get('semester', 'الأول'),
            'academic_year': data.get('academic_year', '1447هـ')
        }
        
        # التعديل الأساسي: نضمن خلط الخيارات دائماً عند تعدد النماذج لكسر نمط الإجابات
        shuffle_options = True if len(models) > 1 else data.get('shuffle_options', True)
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد أسئلة'}), 400
        
        # جلب الأسئلة
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        # تحويل الأسئلة لقاموس (كما في كودك الأصلي)
        # مع تنسيق النص للطباعة (تحويل \n إلى <br> ومنع كسر الأسطر)
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': format_text_for_print(getattr(q, 'question_text', '') or ''),
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': format_text_for_print(getattr(opt, 'option_text', '') or ''),
                    'image_url': getattr(opt, 'image_url', None) or '',
                    'is_correct': getattr(opt, 'is_correct', False)
                })
            questions_data.append(q_dict)
        
        # جلب إعدادات الهيدر (كما في كودك الأصلي)
        settings = ExamHeaderSettings.query.first()
        header_settings = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'time': settings.time if settings else '',
            'grade': settings.grade if settings else '',
            'total_score': settings.total_score if settings else 30,
            'checker_name': settings.checker_name if settings else '',
            'reviewer_name': settings.reviewer_name if settings else ''
        }
        
        # تحويل الشعار لـ base64 (كما في كودك الأصلي)
        logo_base64 = None
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode('utf-8')}"
        except Exception as logo_err:
            current_app.logger.warning(f"Could not load logo: {logo_err}")
        
        header_settings['logo_base64'] = logo_base64
        
        # توليد HTML لكل نموذج
        all_models_html = []
        answer_keys = {}
        letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        
        for idx, model_letter in enumerate(models):
            # 🔧 seed يعتمد على: محتوى الأسئلة + النموذج + رقم عشوائي كبير
            question_ids_str = ''.join(str(q['question_id']) for q in questions_data)
            random_offset = [15485863, 32452843, 49979687, 67867967][idx % 4]
            seed = (hash(question_ids_str + model_letter) + idx * 7919 + random_offset) % (2**31)
            
            # التحقق من وجود ترتيب محفوظ (للنموذج الأول فقط)
            has_saved_order = saved_options_order and len(saved_options_order) > 0 and idx == 0
            
            current_app.logger.info(f"Model {model_letter}: has_saved_order={has_saved_order}, saved_options_order keys={list(saved_options_order.keys())[:5] if saved_options_order else 'None'}")
            
            shuffled_questions = shuffle_exam(
                questions_data,
                shuffle_questions=not has_saved_order,  # لا تخلط الأسئلة إذا فيه ترتيب محفوظ
                shuffle_options=shuffle_options if not has_saved_order else True,  # استخدم الترتيب المحفوظ
                seed=seed if not has_saved_order else None,
                saved_options_order=saved_options_order if has_saved_order else None
            )
            
            # بناء مفتاح الإجابات من الأسئلة المخلوطة لهذا النموذج تحديداً
            model_answers = []
            for q in shuffled_questions:
                correct_letter = ''
                # البحث عن الإجابة الصحيحة بعد الخلط (هذا يضمن اختلاف الحرف بين النماذج)
                for i, opt in enumerate(q.get('options', [])):
                    if opt.get('is_correct'):
                        correct_letter = letters[i] if i < len(letters) else str(i+1)
                        break
                model_answers.append({'answer': correct_letter})
            answer_keys[model_letter] = model_answers
            
            # توليد QR code (كما في كودك الأصلي)
            qr_code_data = None
            if include_barcode:
                qr_data = {
                    'subject': header_settings.get('subject', ''),
                    'model': model_letter,
                    'questions': len(questions_data),
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                qr_code_data = generate_qr_code(qr_data)
            
            # توليد HTML للنموذج (كما في كودك الأصلي)
            model_html = render_template(
                'question/exam_paper_layout_with_barcode.html',
                questions=shuffled_questions,
                model_letter=model_letter,
                qr_code=qr_code_data,
                show_answers=include_answers,
                exam_title=f"نموذج الاختبار - {model_letter}",
                font_size=font_size,
                image_size=image_size,
                columns=columns,
                spacing=spacing,
                options_layout=options_layout,
                header_format=header_format,
                **header_settings
            )
            
            all_models_html.append(model_html)
        
        # إضافة بطاقة التصحيح (كما في كودك الأصلي)
        if include_answer_sheet:
            answer_sheet_html = render_template(
                'question/answer_sheet_template.html',
                answer_keys=answer_keys,
                models=models,
                questions_count=len(questions_data),
                **header_settings
            )
            all_models_html.append(answer_sheet_html)
        
        # دمج كل النماذج في HTML واحد للطباعة (كما في كودك الأصلي)
        combined_html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>النماذج المتعددة</title>
<style>
@media print {
    .page-break { page-break-after: always; }
    .no-print { display: none; }
}
@page { size: A4; margin: 15mm; }
.print-btn {
    position: fixed;
    top: 10px;
    left: 10px;
    padding: 15px 30px;
    background: #4CAF50;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
    z-index: 9999;
}
.print-btn:hover { background: #45a049; }

/* === تنسيق الأسطر لمنع كسر المعادلات الكيميائية === */
.line-block {
    display: inline-block;
    white-space: nowrap;
}
</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">🖨️ طباعة النماذج</button>
"""
        
        for i, model_html in enumerate(all_models_html):
            combined_html += model_html
            if i < len(all_models_html) - 1:
                combined_html += '<div class="page-break"></div>'
        
        # إضافة سكربت لحفظ ترتيب الخيارات في النافذة الأصلية
        # نبني ترتيب الخيارات من النموذج الأول فقط
        first_model_order = {}
        if all_models_html and questions_data:
            # نستخدم الأسئلة المخلوطة من أول نموذج
            first_shuffled = shuffle_exam(
                questions_data,
                shuffle_questions=True if not saved_options_order else False,
                shuffle_options=shuffle_options,
                seed=(hash(''.join(str(q['question_id']) for q in questions_data) + models[0]) + 15485863) % (2**31) if not saved_options_order else None,
                saved_options_order=saved_options_order if saved_options_order else None
            )
            for q in first_shuffled:
                qid = str(q.get('question_id', ''))
                options = q.get('options', [])
                first_model_order[qid] = [opt.get('option_id') for opt in options]
        
        # إضافة السكربت لإرسال الترتيب للنافذة الأصلية
        options_order_json = json.dumps(first_model_order, ensure_ascii=False)
        combined_html += f'''
<script>
// إرسال ترتيب الخيارات للنافذة الأصلية
if (window.opener && !window.opener.closed) {{
    window.opener.shuffledOptionsOrder = {options_order_json};
    console.log('تم حفظ ترتيب الخيارات:', window.opener.shuffledOptionsOrder);
}}
</script>
'''
        
        combined_html += "</body></html>"
        
        return combined_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
    except Exception as e:
        current_app.logger.exception(f"Error previewing multi models: {e}")
        return jsonify({'error': str(e)}), 500


# 1. دالة المعاينة: قراءة ملف الإكسل وتمرير البيانات للواجهة
@question_bp.route('/preview-students', methods=['POST'])
@login_required
def preview_students():
    # تعريف القائمة في البداية لتجنب خطأ التعريف "not defined"
    final_students = [] 
    try:
        file = request.files.get('student_file')
        if not file:
            return jsonify({'error': 'الرجاء اختيار ملف إكسل'}), 400
        
        df = pd.read_excel(file)
        # تنظيف أسماء الأعمدة من المسافات
        df.columns = [str(c).strip() for c in df.columns]
        
        for _, row in df.iterrows():
            # البحث عن البيانات بمسميات مرنة (عربي/إنجليزي) لضمان القراءة
            name = row.get('الاسم') or row.get('اسم الطالب') or row.get('Name') or '..........'
            academic_id = row.get('الرقم الأكاديمي') or row.get('الرقم الاكاديمي') or row.get('Academic ID') or '..........'
            section = row.get('الشعبة') or row.get('الشعبه') or row.get('Section') or '....'
            
            # استخدام مفاتيح إنجليزية لتطابق قالب HTML (student.name)
            final_students.append({
                'name': str(name),
                'academic_id': str(academic_id),
                'section': str(section)
            })
        
        return jsonify({'success': True, 'students': final_students})
    except Exception as e:
        current_app.logger.error(f"Error in preview_students: {str(e)}")
        return jsonify({'error': f'خطأ في معالجة الملف: {str(e)}'}), 500

# ============================================================
# دالة توليد باركود الرقم الأكاديمي
# ============================================================
def generate_student_barcode(academic_id):
    """
    توليد باركود Code39 للرقم الأكاديمي
    
    Args:
        academic_id: الرقم الأكاديمي للطالب (string أو int)
        
    Returns:
        Base64 string للصورة
    """
    try:
        # تحويل الرقم لنص وإزالة المسافات
        academic_id_str = str(academic_id).strip()
        
        if not academic_id_str or academic_id_str == 'None':
            return None
        
        # إنشاء باركود Code39
        code39 = barcode.get_barcode_class('code39')
        
        # إعدادات الباركود
        writer = ImageWriter()
        writer.set_options({
            'module_width': 0.5,
            'module_height': 18,
            'quiet_zone': 4,
            'font_size': 0,
            'text_distance': 18,
            'write_text': True
        })
        
        # إنشاء الباركود
        barcode_obj = code39(academic_id_str, writer=writer, add_checksum=False)
        
        # حفظ في الذاكرة
        buffer = io.BytesIO()
        barcode_obj.write(buffer)
        buffer.seek(0)
        
        # تحويل لـ Base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        current_app.logger.error(f"Error generating barcode for {academic_id}: {e}")
        return None


# 2. دالة الطباعة: توليد أوراق Remark بناءً على الكليشة والأسماء المرفوعة
@question_bp.route('/print-remark-sheets', methods=['POST'])
@login_required
def print_remark_sheets():
    """طباعة أوراق إجابة ريمارك مع الباركود"""
    try:
        data = request.get_json()
        students_list = data.get('students', [])
        exam_type = data.get('exam_type', 'نهاية')
        semester = data.get('semester', 'الأول')
        academic_year = data.get('academic_year', '1447هـ')
        
        # جلب إعدادات الكليشة من قاعدة البيانات
        settings = ExamHeaderSettings.query.first()
        
        header_context = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'grade': settings.grade if settings else '',
            'total_score': settings.total_score if settings else 30,
            'exam_type': exam_type,
            'semester': semester,
            'academic_year': academic_year,
            'logo_base64': ''
        }

        # تحويل الشعار لـ Base64
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    header_context['logo_base64'] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            current_app.logger.warning(f"Could not load logo: {e}")

        all_html = ""
        for student in students_list:
            # توليد الباركود للرقم الأكاديمي
            academic_id = student.get('academic_id', '')
            if academic_id:
                student['barcode'] = generate_student_barcode(academic_id)
            else:
                student['barcode'] = None
            
            # توليد HTML للطالب
            all_html += render_template('question/remark_answer_sheet.html', 
                                       student=student, 
                                       **header_context)
            all_html += '<div style="page-break-after: always;"></div>'

        return jsonify({'success': True, 'html_content': all_html})
        
    except Exception as e:
        current_app.logger.error(f"Error in print_remark_sheets: {str(e)}")
        return jsonify({'error': f'فشل تجهيز الطباعة: {str(e)}'}), 500


# ==================== Route لاستخراج مفتاح إجابة OMR ====================
@question_bp.route('/generate-omr-answer-key', methods=['POST'])
@login_required
def generate_omr_answer_key():
    """استخراج مفتاح إجابة OMR من الأسئلة المختارة"""
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        model_letter = data.get('model_letter', 'أ')
        exam_type = data.get('exam_type', 'نهاية')
        semester = data.get('semester', 'الأول')
        academic_year = data.get('academic_year', '1447هـ')
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد أسئلة'}), 400
        
        # جلب الأسئلة مع الخيارات
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        # استخراج الإجابات الصحيحة
        answers = {}
        letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        
        for i, q in enumerate(questions, 1):
            for j, opt in enumerate(q.options):
                if opt.is_correct:
                    answers[i] = letters[j] if j < len(letters) else 'أ'
                    break
        
        # جلب إعدادات الكليشة
        header_settings_record = ExamHeaderSettings.query.first()
        header_settings = {
            'country': 'المملكة العربية السعودية',
            'ministry': 'وزارة التعليم',
            'education_department': '',
            'school_name': '',
            'subject': '',
            'time': '',
            'grade': '',
            'total_score': 30,
            'logo_base64': ''
        }
        if header_settings_record:
            header_settings.update({
                'country': getattr(header_settings_record, 'country', 'المملكة العربية السعودية'),
                'ministry': getattr(header_settings_record, 'ministry', 'وزارة التعليم'),
                'education_department': getattr(header_settings_record, 'education_department', ''),
                'school_name': getattr(header_settings_record, 'school_name', ''),
                'subject': getattr(header_settings_record, 'subject', ''),
                'time': getattr(header_settings_record, 'time', ''),
                'grade': getattr(header_settings_record, 'grade', ''),
                'total_score': getattr(header_settings_record, 'total_score', 30)
            })
        
        # تحويل الشعار لـ Base64
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    header_settings['logo_base64'] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            current_app.logger.warning(f"Could not load logo: {e}")
        
        # توليد HTML لمفتاح الإجابة
        answer_key_html = render_template(
            'question/remark_answer_sheet.html',
            student={'name': '🔑 مفتاح الإجابة', 'academic_id': '---', 'section': '---', 'barcode': None},
            is_answer_key=True,
            answers=answers,
            model_letter=model_letter,
            exam_type=exam_type,
            semester=semester,
            academic_year=academic_year,
            questions_count=len(questions),
            **header_settings
        )
        
        # إضافة زر الطباعة - بدون header ثابت لتجنب انزياح الأوراق
        full_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>🔑 مفتاح إجابة OMR - النموذج {model_letter}</title>
<style>
@media print {{
    .no-print {{ display: none !important; }}
}}
@media screen {{
    .screen-only-header {{
        background: #c41e3a;
        color: white;
        padding: 15px 20px;
        text-align: center;
        margin-bottom: 20px;
        border-radius: 8px;
    }}
    .screen-only-header button {{
        background: white;
        color: #c41e3a;
        border: none;
        padding: 10px 25px;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 10px;
    }}
    .screen-only-header button:hover {{
        background: #f0f0f0;
    }}
}}
body {{
    margin: 0;
    padding: 0;
}}
</style>
</head>
<body>
<div class="screen-only-header no-print">
    <button onclick="window.print()">🖨️ طباعة مفتاح الإجابة</button>
    <div style="margin-top: 10px;">🔑 مفتاح إجابة OMR - النموذج {model_letter} - عدد الأسئلة: {len(questions)}</div>
</div>
{answer_key_html}
</body>
</html>"""
        
        return jsonify({'success': True, 'html': full_html})
        
    except Exception as e:
        current_app.logger.exception(f"Error generating OMR answer key: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/print-remark-sheets-multi-models', methods=['POST'])
@login_required
def print_remark_sheets_multi_models():
    """طباعة أوراق إجابة ريمارك للنماذج المتعددة"""
    try:
        data = request.get_json()
        students_list = data.get('students', [])
        models = data.get('models', ['أ'])  # النماذج المطلوبة
        question_ids = data.get('question_ids', [])
        shuffle_options = data.get('shuffle_options', True)
        exam_type = data.get('exam_type', 'نهاية')
        semester = data.get('semester', 'الأول')
        academic_year = data.get('academic_year', '1447هـ')
        
        if not students_list:
            return jsonify({'error': 'لم يتم تحديد قائمة الطلاب'}), 400
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد الأسئلة'}), 400
        
        # جلب الأسئلة
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        # تحويل الأسئلة لقاموس مع تنسيق النص للطباعة
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': format_text_for_print(getattr(q, 'question_text', '') or ''),
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': format_text_for_print(getattr(opt, 'option_text', '') or ''),
                    'image_url': getattr(opt, 'image_url', None) or '',
                    'is_correct': getattr(opt, 'is_correct', False)
                })
            questions_data.append(q_dict)
        
        # جلب إعدادات الكليشة
        settings = ExamHeaderSettings.query.first()
        header_context = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'grade': settings.grade if settings else '',
            'total_score': settings.total_score if settings else 30,
            'exam_type': exam_type,
            'semester': semester,
            'academic_year': academic_year,
            'logo_base64': ''
        }

        # تحويل الشعار لـ Base64
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    header_context['logo_base64'] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            current_app.logger.warning(f"Could not load logo: {e}")
        
        # توليد مفاتيح الإجابة لكل نموذج
        answer_keys = {}
        letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        
        for idx, model_letter in enumerate(models):
            # 🔧 seed يعتمد على: محتوى الأسئلة + النموذج + رقم عشوائي كبير
            question_ids_str = ''.join(str(q['question_id']) for q in questions_data)
            random_offset = [15485863, 32452843, 49979687, 67867967][idx % 4]
            seed = (hash(question_ids_str + model_letter) + idx * 7919 + random_offset) % (2**31)
            shuffled_questions = shuffle_exam(
                questions_data,
                shuffle_questions=True,
                shuffle_options=shuffle_options,
                seed=seed
            )
            
            # بناء مفتاح الإجابات لهذا النموذج
            model_answers = {}
            for q_num, q in enumerate(shuffled_questions, 1):
                correct_letter = ''
                for i, opt in enumerate(q.get('options', [])):
                    if opt.get('is_correct'):
                        correct_letter = letters[i] if i < len(letters) else str(i+1)
                        break
                model_answers[q_num] = correct_letter
            answer_keys[model_letter] = model_answers
        
        # توزيع النماذج على الطلاب بالتساوي
        students_per_model = len(students_list) // len(models)
        remainder = len(students_list) % len(models)
        
        all_html = ""
        student_idx = 0
        
        for model_idx, model_letter in enumerate(models):
            # عدد الطلاب لهذا النموذج
            count = students_per_model + (1 if model_idx < remainder else 0)
            
            for _ in range(count):
                if student_idx >= len(students_list):
                    break
                    
                student = students_list[student_idx]
                student_idx += 1
                
                # توليد الباركود للرقم الأكاديمي
                academic_id = student.get('academic_id', '')
                if academic_id:
                    student['barcode'] = generate_student_barcode(academic_id)
                else:
                    student['barcode'] = None
                
                # إضافة معلومات النموذج
                student['model_letter'] = model_letter
                
                # توليد HTML للطالب مع مفتاح إجابات النموذج
                all_html += render_template(
                    'question/remark_answer_sheet.html', 
                    student=student,
                    model_letter=model_letter,
                    is_answer_key=False,
                    answers=None,  # لا نعرض الإجابات في ورقة الطالب
                    questions_count=len(questions_data),
                    **header_context
                )
                all_html += '<div style="page-break-after: always;"></div>'
        
        # إضافة مفاتيح الإجابة لكل نموذج في النهاية
        for model_letter in models:
            all_html += render_template(
                'question/remark_answer_sheet.html',
                student={
                    'name': f'🔑 مفتاح الإجابة - نموذج {model_letter}',
                    'academic_id': '---',
                    'section': '---',
                    'barcode': None,
                    'model_letter': model_letter
                },
                is_answer_key=True,
                answers=answer_keys[model_letter],
                model_letter=model_letter,
                questions_count=len(questions_data),
                **header_context
            )
            all_html += '<div style="page-break-after: always;"></div>'

        return jsonify({'success': True, 'html_content': all_html})
        
    except Exception as e:
        current_app.logger.error(f"Error in print_remark_sheets_multi_models: {str(e)}")
        return jsonify({'error': f'فشل تجهيز الطباعة: {str(e)}'}), 500


@question_bp.route('/print-blank-remark-sheets', methods=['POST'])
@login_required
def print_blank_remark_sheets():
    """طباعة نماذج ريمارك فارغة للنماذج المتعددة"""
    try:
        data = request.get_json()
        models = data.get('models', ['أ'])
        count_per_model = data.get('count_per_model', 10)
        question_ids = data.get('question_ids', [])
        exam_type = data.get('exam_type', 'نهاية')
        semester = data.get('semester', 'الأول')
        academic_year = data.get('academic_year', '1447هـ')
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد الأسئلة'}), 400
        
        # جلب الأسئلة لمعرفة العدد
        questions = get_ordered_questions(question_ids)
        questions_count = len(questions)
        
        # جلب إعدادات الكليشة
        settings = ExamHeaderSettings.query.first()
        header_context = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'grade': settings.grade if settings else '',
            'total_score': settings.total_score if settings else 30,
            'exam_type': exam_type,
            'semester': semester,
            'academic_year': academic_year,
            'logo_base64': ''
        }

        # تحويل الشعار لـ Base64
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    header_context['logo_base64'] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            current_app.logger.warning(f"Could not load logo: {e}")
        
        all_html = ""
        
        # توليد نماذج فارغة لكل نموذج
        for model_letter in models:
            for i in range(count_per_model):
                blank_student = {
                    'name': '..........................................',
                    'academic_id': '..........................................',
                    'section': '.....',
                    'barcode': None,
                    'model_letter': model_letter
                }
                
                all_html += render_template(
                    'question/remark_answer_sheet.html',
                    student=blank_student,
                    model_letter=model_letter,
                    is_answer_key=False,
                    answers=None,
                    questions_count=questions_count,
                    **header_context
                )
                all_html += '<div style="page-break-after: always;"></div>'
        
        return jsonify({'success': True, 'html_content': all_html})
        
    except Exception as e:
        current_app.logger.error(f"Error in print_blank_remark_sheets: {str(e)}")
        return jsonify({'error': f'فشل تجهيز الطباعة: {str(e)}'}), 500


@question_bp.route('/generate-all-models-answer-keys', methods=['POST'])
@login_required
def generate_all_models_answer_keys():
    """استخراج مفاتيح إجابة OMR لكل النماذج"""
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        models = data.get('models', ['أ'])
        shuffle_options = data.get('shuffle_options', True)
        exam_type = data.get('exam_type', 'نهاية')
        semester = data.get('semester', 'الأول')
        academic_year = data.get('academic_year', '1447هـ')
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد أسئلة'}), 400
        
        # جلب الأسئلة
        questions = get_ordered_questions(question_ids)
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        # تحويل الأسئلة لقاموس مع تنسيق النص للطباعة
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': format_text_for_print(getattr(q, 'question_text', '') or ''),
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': format_text_for_print(getattr(opt, 'option_text', '') or ''),
                    'image_url': getattr(opt, 'image_url', None) or '',
                    'is_correct': getattr(opt, 'is_correct', False)
                })
            questions_data.append(q_dict)
        
        # جلب إعدادات الكليشة
        header_settings_record = ExamHeaderSettings.query.first()
        header_settings = {
            'country': 'المملكة العربية السعودية',
            'ministry': 'وزارة التعليم',
            'education_department': '',
            'school_name': '',
            'subject': '',
            'time': '',
            'grade': '',
            'total_score': 30,
            'logo_base64': ''
        }
        if header_settings_record:
            header_settings.update({
                'country': getattr(header_settings_record, 'country', 'المملكة العربية السعودية'),
                'ministry': getattr(header_settings_record, 'ministry', 'وزارة التعليم'),
                'education_department': getattr(header_settings_record, 'education_department', ''),
                'school_name': getattr(header_settings_record, 'school_name', ''),
                'subject': getattr(header_settings_record, 'subject', ''),
                'time': getattr(header_settings_record, 'time', ''),
                'grade': getattr(header_settings_record, 'grade', ''),
                'total_score': getattr(header_settings_record, 'total_score', 30)
            })
        
        # تحويل الشعار لـ Base64
        try:
            logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    header_settings['logo_base64'] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            current_app.logger.warning(f"Could not load logo: {e}")
        
        # توليد مفاتيح الإجابة لكل نموذج
        all_keys_html = ""
        letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        
        for idx, model_letter in enumerate(models):
            # 🔧 seed يعتمد على: محتوى الأسئلة + النموذج + رقم عشوائي كبير
            question_ids_str = ''.join(str(q['question_id']) for q in questions_data)
            random_offset = [15485863, 32452843, 49979687, 67867967][idx % 4]
            seed = (hash(question_ids_str + model_letter) + idx * 7919 + random_offset) % (2**31)
            shuffled_questions = shuffle_exam(
                questions_data,
                shuffle_questions=True,
                shuffle_options=shuffle_options,
                seed=seed
            )
            
            # استخراج الإجابات الصحيحة
            answers = {}
            for q_num, q in enumerate(shuffled_questions, 1):
                correct_letter = ''
                for i, opt in enumerate(q.get('options', [])):
                    if opt.get('is_correct'):
                        correct_letter = letters[i] if i < len(letters) else str(i+1)
                        break
                answers[q_num] = correct_letter
            
            # توليد HTML لمفتاح الإجابة
            answer_key_html = render_template(
                'question/remark_answer_sheet.html',
                student={'name': f'🔑 مفتاح الإجابة - نموذج {model_letter}', 'academic_id': '---', 'section': '---', 'barcode': None},
                is_answer_key=True,
                answers=answers,
                model_letter=model_letter,
                exam_type=exam_type,
                semester=semester,
                academic_year=academic_year,
                questions_count=len(questions),
                **header_settings
            )
            all_keys_html += answer_key_html
            if idx < len(models) - 1:
                all_keys_html += '<div style="page-break-after: always;"></div>'
        
        # إضافة زر الطباعة - بدون header ثابت لتجنب انزياح الأوراق
        full_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>🔑 مفاتيح إجابة OMR - النماذج {', '.join(models)}</title>
<style>
@media print {{
    .no-print {{ display: none !important; }}
}}
@media screen {{
    .screen-only-header {{
        background: #9c27b0;
        color: white;
        padding: 15px 20px;
        text-align: center;
        margin-bottom: 20px;
        border-radius: 8px;
    }}
    .screen-only-header button {{
        background: white;
        color: #9c27b0;
        border: none;
        padding: 10px 25px;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 10px;
    }}
    .screen-only-header button:hover {{
        background: #f0f0f0;
    }}
}}
body {{
    margin: 0;
    padding: 0;
}}
</style>
</head>
<body>
<div class="screen-only-header no-print">
    <button onclick="window.print()">🖨️ طباعة مفاتيح الإجابة</button>
    <div style="margin-top: 10px;">🔑 مفاتيح إجابة OMR - النماذج: {', '.join(models)} - عدد الأسئلة: {len(questions)}</div>
</div>
{all_keys_html}
</body>
</html>"""
        
        return jsonify({'success': True, 'html': full_html})
        
    except Exception as e:
        current_app.logger.exception(f"Error generating all models answer keys: {e}")
        return jsonify({'error': str(e)}), 500


# =====================================================
# ===== صفحة تصنيف الأسئلة بالذكاء الاصطناعي =====
# =====================================================

@question_bp.route('/classify')
@login_required
def classify_questions():
    """
    صفحة تصنيف الأسئلة بالذكاء الاصطناعي
    تعرض إحصائيات التصنيف وتتيح التصنيف التلقائي والتعديل اليدوي
    """
    return render_template('classify_questions.html')


# =====================================================
# ===== APIs حفظ واسترجاع الاختبارات =====
# =====================================================

@question_bp.route('/saved-exams', methods=['GET'])
@login_required
def get_saved_exams():
    """جلب قائمة الاختبارات المحفوظة"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        course_id = request.args.get('course_id', type=int)
        search = request.args.get('search', '')
        
        query = SavedExam.query.filter_by(is_active=True)
        
        if course_id:
            query = query.filter_by(course_id=course_id)
        
        if search:
            query = query.filter(SavedExam.name.ilike(f'%{search}%'))
        
        query = query.order_by(SavedExam.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'exams': [exam.to_dict() for exam in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching saved exams: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@question_bp.route('/saved-exams', methods=['POST'])
@login_required
def save_exam():
    """حفظ اختبار جديد"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'اسم الاختبار مطلوب'}), 400
        
        question_ids = data.get('question_ids', [])
        if not question_ids:
            return jsonify({'success': False, 'error': 'يجب اختيار أسئلة للحفظ'}), 400
        
        # الحصول على ترتيب الخيارات لكل سؤال (إذا كان موجوداً)
        questions_with_order = data.get('questions_with_order', [])
        options_order = {}
        for q in questions_with_order:
            if q.get('options_order'):
                options_order[str(q['question_id'])] = q['options_order']
        
        # إنشاء الاختبار الجديد
        new_exam = SavedExam(
            name=name,
            description=data.get('description', ''),
            course_id=data.get('course_id'),
            unit_id=data.get('unit_id'),
            question_ids=question_ids,
            questions_count=len(question_ids),
            models=data.get('models', ['أ']),
            settings={
                'shuffle_questions': data.get('shuffle_questions', True),
                'shuffle_options': data.get('shuffle_options', True),
                'font_size': data.get('font_size', 14),
                'image_size': data.get('image_size', 100),
                'columns': data.get('columns', 2),
                'spacing': data.get('spacing', 'normal'),
                'options_layout': data.get('options_layout', 'vertical'),
                'options_order': options_order  # ترتيب الخيارات المخلوط لكل سؤال
            },
            header_settings=data.get('header_settings', {}),
            exam_type=data.get('exam_type', ''),
            semester=data.get('semester', ''),
            academic_year=data.get('academic_year', ''),
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        
        db.session.add(new_exam)
        db.session.commit()
        
        current_app.logger.info(f"Exam saved: {new_exam.id} - {new_exam.name}")
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ الاختبار بنجاح',
            'exam': new_exam.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving exam: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@question_bp.route('/saved-exams/<int:exam_id>', methods=['GET'])
@login_required
def get_saved_exam(exam_id):
    """جلب تفاصيل اختبار محفوظ"""
    try:
        exam = SavedExam.query.filter_by(id=exam_id, is_active=True).first()
        
        if not exam:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        return jsonify({
            'success': True,
            'exam': exam.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching exam {exam_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@question_bp.route('/saved-exams/<int:exam_id>', methods=['PUT'])
@login_required
def update_saved_exam(exam_id):
    """تحديث اختبار محفوظ"""
    try:
        exam = SavedExam.query.filter_by(id=exam_id, is_active=True).first()
        
        if not exam:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            exam.name = data['name'].strip()
        if 'description' in data:
            exam.description = data['description']
        if 'question_ids' in data:
            exam.question_ids = data['question_ids']
            exam.questions_count = len(data['question_ids'])
        if 'models' in data:
            exam.models = data['models']
        if 'settings' in data:
            exam.settings = data['settings']
        if 'header_settings' in data:
            exam.header_settings = data['header_settings']
        if 'exam_type' in data:
            exam.exam_type = data['exam_type']
        if 'semester' in data:
            exam.semester = data['semester']
        if 'academic_year' in data:
            exam.academic_year = data['academic_year']
        
        exam.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم تحديث الاختبار بنجاح',
            'exam': exam.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating exam {exam_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@question_bp.route('/saved-exams/<int:exam_id>', methods=['DELETE'])
@login_required
def delete_saved_exam(exam_id):
    """حذف اختبار محفوظ (حذف ناعم)"""
    try:
        exam = SavedExam.query.filter_by(id=exam_id, is_active=True).first()
        
        if not exam:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        # حذف ناعم
        exam.is_active = False
        exam.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حذف الاختبار بنجاح'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting exam {exam_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@question_bp.route('/saved-exams/<int:exam_id>/load', methods=['POST'])
@login_required
def load_saved_exam(exam_id):
    """تحميل اختبار محفوظ مع جلب الأسئلة بنفس الترتيب المحفوظ"""
    try:
        exam = SavedExam.query.filter_by(id=exam_id, is_active=True).first()
        
        if not exam:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        # جلب الأسئلة المحفوظة بنفس الترتيب الأصلي
        saved_question_ids = exam.question_ids or []
        
        # جلب ترتيب الخيارات المحفوظ (إذا وجد)
        settings = exam.settings or {}
        options_order = settings.get('options_order', {})
        
        # جلب جميع الأسئلة دفعة واحدة
        questions_dict = {}
        if saved_question_ids:
            questions = Question.query.filter(
                Question.question_id.in_(saved_question_ids)
            ).options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit)
            ).all()
            
            # تحويل لقاموس للوصول السريع
            for q in questions:
                questions_dict[q.question_id] = q
        
        # بناء قائمة الأسئلة بنفس الترتيب المحفوظ
        questions_data = []
        for qid in saved_question_ids:
            q = questions_dict.get(qid)
            if q:  # السؤال موجود
                # جلب الخيارات
                options_list = []
                for opt in q.options:
                    options_list.append({
                        'option_id': getattr(opt, 'option_id', None),
                        'option_text': getattr(opt, 'option_text', '') or '',
                        'image_url': getattr(opt, 'image_url', None) or '',
                        'is_correct': getattr(opt, 'is_correct', False)
                    })
                
                # إذا كان هناك ترتيب محفوظ للخيارات، نرتبها حسبه
                saved_order = options_order.get(str(qid))
                if saved_order and len(saved_order) == len(options_list):
                    # إنشاء قاموس للخيارات حسب الـ ID
                    options_by_id = {opt['option_id']: opt for opt in options_list}
                    # ترتيب الخيارات حسب الترتيب المحفوظ
                    ordered_options = []
                    for opt_id in saved_order:
                        if opt_id in options_by_id:
                            ordered_options.append(options_by_id[opt_id])
                    # إذا تم ترتيب جميع الخيارات بنجاح
                    if len(ordered_options) == len(options_list):
                        options_list = ordered_options
                
                q_dict = {
                    'question_id': q.question_id,
                    'question_text': q.question_text or '',
                    'image_url': getattr(q, 'image_url', None) or '',
                    'difficulty': getattr(q, 'difficulty', 'medium'),
                    'bloom_level': getattr(q, 'bloom_level', 'remember'),
                    'unit': q.lesson.unit.name if q.lesson and q.lesson.unit else 'غير محدد',
                    'lesson': q.lesson.name if q.lesson else 'غير محدد',
                    'options': options_list
                }
                questions_data.append(q_dict)
        
        return jsonify({
            'success': True,
            'exam': exam.to_dict(),
            'questions': questions_data,
            'options_order': options_order  # إرسال ترتيب الخيارات للـ Frontend
        })
        
    except Exception as e:
        current_app.logger.error(f"Error loading exam {exam_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Export Courses/Units/Lessons list route --- #
@question_bp.route("/export/courses_units_lessons")
@login_required
def export_courses_units_lessons():
    """
    تصدير قائمة بجميع المناهج والوحدات والدروس المتاحة في النظام
    """
    try:
        # جلب جميع الدروس مع علاقاتها
        lessons = Lesson.query.join(Unit).join(Course).order_by(
            Course.name,
            Unit.order_num,
            Lesson.order_num
        ).all()
        
        # إنشاء قائمة بالبيانات
        data = []
        for lesson in lessons:
            data.append({
                "Course Name": lesson.unit.course.name,
                "Unit Name": lesson.unit.name,
                "Lesson Name": lesson.name
            })
        
        # إنشاء DataFrame
        df = pd.DataFrame(data)
        
        # إزالة التكرارات (اختياري - يمكن إبقاء التكرارات لتوضيح جميع الدروس)
        # df = df.drop_duplicates()
        
        # إنشاء BytesIO object
        output = io.BytesIO()
        
        # كتابة DataFrame إلى BytesIO
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Courses_Units_Lessons')
            
            # ضبط عرض الأعمدة
            worksheet = writer.sheets['Courses_Units_Lessons']
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                col_letter = chr(65 + i) if i < 26 else chr(65 + i // 26 - 1) + chr(65 + i % 26)
                worksheet.column_dimensions[col_letter].width = max_width
        
        output.seek(0)
        
        # إرسال الملف
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='courses_units_lessons.xlsx'
        )
        
    except Exception as e:
        current_app.logger.exception(f"Error exporting courses/units/lessons list: {e}")
        flash(f"حدث خطأ أثناء تصدير قائمة المناهج والوحدات والدروس: {str(e)}", "danger")
        return redirect(url_for("question.import_questions"))
