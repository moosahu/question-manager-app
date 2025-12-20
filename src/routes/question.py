import os
import logging
import time
import uuid
import io # Added for reading/writing file in memory
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
except ImportError:
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
except ImportError:
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

# إضافة استيراد نظام الإشعارات
try:
    from src.utils.notification_system import QuestionNotifications, SystemNotifications
    notifications_available = True
except ImportError:
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
    "Question Text", "Question Image URL",
    "Option 1 Text", "Option 1 Image URL",
    "Option 2 Text", "Option 2 Image URL",
    "Option 3 Text", "Option 3 Image URL",
    "Option 4 Text", "Option 4 Image URL",
    "Correct Option Number"
]

def allowed_image_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS)

def allowed_import_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMPORT_EXTENSIONS)

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
        
        lesson_id = request.form.get("lesson_id")
        if not lesson_id:
            flash("يجب اختيار درس لاستيراد الأسئلة إليه.", "danger")
            current_app.logger.warning("No lesson_id provided in import form.")
            return render_template("question/import_questions.html", lessons=lessons, form=form)
        
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
            
            # Validate columns
            missing_columns = [col for col in EXPECTED_IMPORT_COLUMNS if col not in df.columns]
            if missing_columns:
                flash(f"الملف يفتقد إلى الأعمدة التالية: {', '.join(missing_columns)}", "danger")
                current_app.logger.warning(f"Missing columns in import file: {missing_columns}")
                return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id, form=form)
            
            # Process each row
            imported_count = 0
            error_details = []
            
            for index, row in df.iterrows():
                try:
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
                    
                    # Create question
                    new_question = Question(
                        question_text=question_text,
                        lesson_id=lesson_id,
                        image_url=question_image_url
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
            "Question Text": "ما هي الصيغة الكيميائية للماء؟",
            "Question Image URL": "",
            "Option 1 Text": "H2O",
            "Option 1 Image URL": "",
            "Option 2 Text": "CO2",
            "Option 2 Image URL": "",
            "Option 3 Text": "NaCl",
            "Option 3 Image URL": "",
            "Option 4 Text": "O2",
            "Option 4 Image URL": "",
            "Correct Option Number": 1
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
        
        # تنسيق الأسئلة
        formatted_questions = []
        for question in questions:
            formatted_q = {
                'question_id': question.question_id,
                'question_text': question.question_text,
                'options': [
                    {
                        'option_id': opt.option_id,
                        'option_text': opt.option_text,
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
        questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
        
        if not questions:
            return jsonify({'error': 'لا توجد أسئلة محددة'}), 400
        
        # تحويل الأسئلة
        questions_data = []
        for q in questions:
            q_dict = {'id': q.question_id, 'question_text': q.question_text, 'points': 1, 'options': []}
            for opt in q.options:
                q_dict['options'].append({'option_text': opt.option_text, 'is_correct': opt.is_correct})
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
        
        questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
        
        questions_data = []
        for q in questions:
            q_dict = {'id': q.question_id, 'question_text': q.question_text, 'points': 1, 'options': []}
            for opt in q.options:
                q_dict['options'].append({'option_text': opt.option_text, 'is_correct': opt.is_correct, 'option_id': opt.option_id})
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


def shuffle_exam(questions, shuffle_questions=True, shuffle_options=True, seed=None):
    """
    خلط ترتيب الأسئلة والخيارات
    
    Args:
        questions: قائمة الأسئلة
        shuffle_questions: خلط ترتيب الأسئلة
        shuffle_options: خلط ترتيب الخيارات
        seed: بذرة للعشوائية (لإعادة الإنتاج)
        
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
    
    # خلط ترتيب الخيارات لكل سؤال
    if shuffle_options:
        letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        for question in shuffled:
            options = question.get('options', [])
            if options:
                # خلط الخيارات
                random.shuffle(options)
                
                # تحديث الإجابة الصحيحة بعد الخلط
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
        questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        current_app.logger.info(f"Found {len(questions)} questions in database")
        
        # تحويل الأسئلة لقاموس
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': q.question_text or '',
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': getattr(opt, 'option_text', '') or '',
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
            # خلط الأسئلة بطريقة مختلفة لكل نموذج
            seed = hash(model_letter) + i * 1000
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
        
        # التعديل الأساسي: نضمن خلط الخيارات دائماً عند تعدد النماذج لكسر نمط الإجابات
        shuffle_options = True if len(models) > 1 else data.get('shuffle_options', True)
        
        if not question_ids:
            return jsonify({'error': 'لم يتم تحديد أسئلة'}), 400
        
        # جلب الأسئلة
        questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
        
        if not questions:
            return jsonify({'error': 'لم يتم العثور على الأسئلة'}), 404
        
        # تحويل الأسئلة لقاموس (كما في كودك الأصلي)
        questions_data = []
        for q in questions:
            q_dict = {
                'question_id': q.question_id,
                'question_text': getattr(q, 'question_text', '') or '',
                'image_url': getattr(q, 'image_url', None) or '',
                'options': []
            }
            for opt in q.options:
                q_dict['options'].append({
                    'option_id': getattr(opt, 'option_id', None),
                    'option_text': getattr(opt, 'option_text', '') or '',
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
            # خلط الأسئلة والخيارات (استخدام المنطق الأصلي مع ضمان استقلالية كل نموذج)
            seed = hash(model_letter) + idx * 1000
            shuffled_questions = shuffle_exam(
                questions_data,
                shuffle_questions=True,
                shuffle_options=shuffle_options,
                seed=seed
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
</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">🖨️ طباعة النماذج</button>
"""
        
        for i, model_html in enumerate(all_models_html):
            combined_html += model_html
            if i < len(all_models_html) - 1:
                combined_html += '<div class="page-break"></div>'
        
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
            'module_width': 0.3,
            'module_height': 8,
            'quiet_zone': 2,
            'font_size': 0,
            'text_distance': 1,
            'write_text': False
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
        
        # جلب إعدادات الكليشة من قاعدة البيانات
        settings = ExamHeaderSettings.query.first()
        
        header_context = {
            'country': settings.country if settings else 'المملكة العربية السعودية',
            'ministry': settings.ministry if settings else 'وزارة التعليم',
            'education_department': settings.education_department if settings else '',
            'school_name': settings.school_name if settings else '',
            'subject': settings.subject if settings else '',
            'grade': settings.grade if settings else '',
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