# src/services/survey_pdf.py
"""تصدير استبيان PDF قابل للطباعة (نموذج فاضي — بدون رموز/محاور) — شعار الوزارة اختياري.
يعيد استخدام نفس محرّك Playwright/الخطوط المستخدم بتصدير الاختبار (src/routes/exam_generator.py)
بدل WeasyPrint المباشر — تفادياً لمشكلة فشل Playwright الصامت على Render الموثّقة سابقاً
بتصدير الاختبار (قبلها كل PDF كان يتولّد بـWeasyPrint المعطوب بدون ما ينتبه له أحد).
"""
import os
import uuid
from flask import render_template, current_app
from weasyprint import HTML

try:
    from src.routes.exam_generator import _get_browser, _default_logo_base64, _get_font_data
except ImportError:  # pragma: no cover
    from routes.exam_generator import _get_browser, _default_logo_base64, _get_font_data

LIKERT5_LABELS = ['موافق بشدة', 'موافق', 'محايد', 'غير موافق', 'غير موافق بشدة']


def _build_sections(questions):
    """نفس خوارزمية التجميع المستخدمة بشاشة تعبئة الاستبيان بالتطبيق — فقرات ليكرت متتالية بنفس
    المحور تتجمّع بشبكة واحدة، أي سؤال آخر يُطبع لحاله. بدون أي رمز محور أو رمز فقرة بالمطبوع."""
    sections, current, current_axis = [], [], None
    for q in questions:
        axis = q.get('axis_code') or None
        is_likert = q.get('type') == 'likert5'
        if is_likert and axis and axis == current_axis:
            current.append(q)
        else:
            if current:
                sections.append(current)
            current = [q]
            current_axis = axis if (is_likert and axis) else None
    if current:
        sections.append(current)
    return sections


def _html_to_pdf(html_content, src_dir):
    browser = _get_browser()
    ctx = browser.new_context()
    page = ctx.new_page()
    tmp_path = os.path.join(src_dir, f'_pw_render_{uuid.uuid4().hex}.html')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        page.goto(f"file://{tmp_path}", wait_until='load')
        pdf = page.pdf(
            format='A4', print_background=True,
            margin={'top': '10mm', 'right': '10mm', 'bottom': '14mm', 'left': '10mm'},
        )
    finally:
        ctx.close()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return pdf


def generate_survey_pdf(survey_dict, show_logo=True):
    """survey_dict: نتيجة survey.to_dict(with_questions=True, show_answers=False) — بدون مفتاح إجابات معرفية إطلاقاً"""
    logo_b64 = _default_logo_base64() if show_logo else ''
    sections = _build_sections(survey_dict.get('questions') or [])
    html_content = render_template(
        'question/export_survey.html',
        survey=survey_dict,
        sections=sections,
        likert_labels=LIKERT5_LABELS,
        show_logo=bool(show_logo and logo_b64),
        logo_base64=logo_b64,
        font_regular=_get_font_data('cairo'),
    )
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    try:
        return _html_to_pdf(html_content, src_dir)
    except Exception as e:
        current_app.logger.warning(f"Playwright failed for survey PDF, fallback to WeasyPrint: {e}")
        base_url = f"file://{src_dir}/"
        return HTML(string=html_content, base_url=base_url).write_pdf()
