"""
video_generator.py — نسخة السيرفر من generate_video.py
يعمل على Linux (Render) + macOS
يحفظ الفيديو في /tmp/question_<id>.mp4
"""

import os, json, math, tempfile, requests, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# ==================== المسارات ====================
_STATIC   = os.path.join(os.path.dirname(__file__), '..', 'static')
FONT_AR   = os.path.join(_STATIC, 'fonts', 'Amiri-Regular.ttf')
FONT_MONO = os.path.join(_STATIC, 'fonts', 'Tahoma-Regular.ttf')
LOGO_PATH = os.path.join(_STATIC, 'images', 'logo.png')

# ==================== الإعدادات ====================
W, H      = 1280, 720
FPS       = 24
HEADER_H  = 155
SUB_H     = 58
FOOTER_H  = 44

# ==================== الألوان ====================
BG          = (245, 247, 250)
CARD_WHITE  = (255, 255, 255)
BORDER      = (220, 228, 245)
GRAD_A      = (78,  205, 196)
GRAD_B      = (37,  99,  235)
TEXT_DARK   = (26,  26,  46)
TEXT_GRAY   = (110, 125, 155)
WHITE       = (255, 255, 255)
GREEN       = (17,  153, 142)
GREEN_LIGHT = (220, 248, 235)
GREEN_TEXT  = (15,  110, 75)
RED         = (210, 55,  55)
YELLOW      = (215, 140, 0)
YELLOW_LIGHT= (255, 248, 220)
BLUE        = (37,  99,  235)

COPYRIGHT           = "جميع الحقوق محفوظة 2026 - تطبيق كيم تحصيلي"
ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', 'CwhRBWXzGAHq8TQ4Fs17')

# ============================================================
# أدوات الرسم
# ============================================================

_BIDI_MARKS = str.maketrans('', '', '\u2066\u2069\u202A\u202C\u200E\u200F\u202B\u200F')
_LTR_RUN    = re.compile(r'[^\u0600-\u06FF\s]+(?:[ \t]+[^\u0600-\u06FF\s]+)*')

def clean_for_video(text: str) -> str:
    """
    1. يحذف BiDi control chars المخزّنة في DB (من applyBidiToTextarea)
    2. يلف كل تسلسل غير-عربي يحتوي حروف/أرقام بـ LRE+PDF
       حتى يعاملها python-bidi كـ LTR داخل الفقرة العربية RTL
       → يمنع عكس "12 g" إلى "g 12"
    """
    text = str(text).translate(_BIDI_MARKS)

    def wrap(m):
        s = m.group(0)
        if re.search(r'[A-Za-z0-9]', s):
            return '\u202A' + s + '\u202C'   # LRE + text + PDF
        return s

    return _LTR_RUN.sub(wrap, text)

def ar(text):
    return get_display(arabic_reshaper.reshape(str(text)))

def FA(size):
    return ImageFont.truetype(FONT_AR, size)

def FL(size):
    return ImageFont.truetype(FONT_MONO, size)

def make_gradient(w, h, c1, c2):
    x = np.linspace(0, 1, w, dtype=np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)
    t   = (xv + yv) / 2
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(3):
        arr[:, :, i] = c1[i] + t * (c2[i] - c1[i])
    return Image.fromarray(arr.astype(np.uint8))

def tw(draw, text, f):
    bb = draw.textbbox((0, 0), text, font=f)
    return bb[2] - bb[0]

def draw_ar_center(draw, text, y, f, color):
    t = ar(text)
    w = tw(draw, t, f)
    draw.text(((W - w) // 2, y), t, font=f, fill=color)

def draw_lat_center(draw, text, y, f, color):
    w = tw(draw, text, f)
    draw.text(((W - w) // 2, y), text, font=f, fill=color)

def card(draw, x1, y1, x2, y2, fill=CARD_WHITE, outline=BORDER, r=14, lw=1):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill)
    if outline:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, outline=outline, width=lw)

def paste_logo(img, cx, cy, size=70):
    if not os.path.exists(LOGO_PATH):
        return
    logo   = Image.open(LOGO_PATH).convert("RGBA")
    logo   = logo.resize((size, size), Image.LANCZOS)
    mask   = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(logo, (0, 0))
    result.putalpha(mask)
    img.paste(result, (cx - size // 2, cy - size // 2), result)

def new_frame():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def add_header(img, title, subtitle=""):
    grad = make_gradient(W, HEADER_H + 40, GRAD_A, GRAD_B)
    img.paste(grad, (0, 0))
    draw = ImageDraw.Draw(img)
    pts  = []
    for i in range(W + 1):
        y = HEADER_H + int(16 * math.sin(2 * math.pi * 2 * i / W))
        pts.append((i, y))
    pts += [(W, H), (0, H)]
    draw.polygon(pts, fill=BG)
    paste_logo(img, 52, HEADER_H // 2, size=52)
    draw = ImageDraw.Draw(img)
    draw_ar_center(draw, title, 40, FA(36), WHITE)
    if subtitle:
        draw_ar_center(draw, subtitle, 90, FA(21), (215, 240, 255))

def add_subtitle_bar(img, subtitle_text):
    draw = ImageDraw.Draw(img)
    sy   = H - FOOTER_H - SUB_H
    draw.rectangle([0, sy, W, sy + SUB_H], fill=(30, 35, 60))
    draw.rectangle([0, sy, W, sy + 2],     fill=GRAD_B)
    t = ar(subtitle_text)
    f = FA(20)
    w = tw(draw, t, f)
    draw.text(((W - w) // 2, sy + (SUB_H - 24) // 2), t, font=f, fill=(220, 235, 255))

def add_footer(img):
    draw = ImageDraw.Draw(img)
    fy   = H - FOOTER_H
    draw.rectangle([0, fy, W, H],       fill=(230, 235, 245))
    draw.rectangle([0, fy, W, fy + 2],  fill=GRAD_B)
    paste_logo(img, W - 36, H - FOOTER_H // 2, size=36)
    draw = ImageDraw.Draw(img)
    cr   = ar(COPYRIGHT)
    cw   = tw(draw, cr, FA(16))
    draw.text(((W - cw) // 2, H - 30), cr, font=FA(16), fill=TEXT_GRAY)

def _is_latin(text: str) -> bool:
    if not text:
        return False
    latin  = sum(1 for c in text if ord(c) < 128 and c.isalpha())
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return latin > arabic


# ============================================================
# الشرائح الست
# ============================================================

def slide_title(sub, unit, lesson):
    img  = make_gradient(W, H, GRAD_A, GRAD_B)
    over = Image.new("RGB", (W, H // 2), (20, 55, 170))
    img.paste(over, (0, H // 2))
    draw = ImageDraw.Draw(img)
    paste_logo(img, W // 2, 150, size=150)
    draw = ImageDraw.Draw(img)
    draw_ar_center(draw, "تطبيق كيم تحصيلي", 370, FA(50), WHITE)
    draw_ar_center(draw, f"{unit}  /  {lesson}", 440, FA(28), (210, 240, 255))
    draw_ar_center(draw, "شرح نموذج سؤال", 492, FA(24), (180, 220, 255))
    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


def slide_question(sub, question_text, options, unit, lesson):
    img, _ = new_frame()
    add_header(img, "السؤال", f"{unit}  /  {lesson}")
    draw   = ImageDraw.Draw(img)

    card(draw, 50, HEADER_H + 18, W - 50, HEADER_H + 100,
         fill=CARD_WHITE, outline=BORDER, r=16)
    draw_ar_center(draw, clean_for_video(question_text), HEADER_H + 36, FA(34), TEXT_DARK)

    y = HEADER_H + 118
    for letter, opt_text, _ in options:
        card(draw, 50, y, W - 50, y + 72, fill=CARD_WHITE, outline=BORDER, r=12, lw=1)
        bx, by = W - 98, y + 16
        draw.ellipse([bx, by, bx + 40, by + 40], fill=BLUE)
        lt = ar(letter)
        draw.text((bx + (40 - tw(draw, lt, FA(22))) // 2, by + 8),
                  lt, font=FA(22), fill=WHITE)
        if _is_latin(opt_text):
            draw.text((80, y + 20), opt_text, font=FL(30), fill=TEXT_DARK)
        else:
            t = ar(opt_text)
            draw.text((W - 80 - tw(draw, t, FA(28)), y + 20),
                      t, font=FA(28), fill=TEXT_DARK)
        y += 84

    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


def slide_formula(sub, c, lesson):
    img, _ = new_frame()
    add_header(img, c["title"], lesson)
    draw   = ImageDraw.Draw(img)

    card(draw, 60, HEADER_H + 15, W - 60, HEADER_H + 110, fill=CARD_WHITE, r=16)
    draw_ar_center(draw, c["line1"], HEADER_H + 28, FA(30), TEXT_DARK)
    if c.get("line2"):
        draw_ar_center(draw, c["line2"], HEADER_H + 70, FA(26), TEXT_GRAY)

    sg = make_gradient(W - 120, 115, (17, 130, 120), (40, 200, 100))
    img.paste(sg, (60, HEADER_H + 125))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([60, HEADER_H + 125, W - 60, HEADER_H + 240],
                            radius=18, outline=GREEN, width=2)
    draw_ar_center(draw, c.get("title", ""), HEADER_H + 133, FA(24), WHITE)
    formula = c.get("formula", "")
    if c.get("formula_is_latin"):
        draw_lat_center(draw, formula, HEADER_H + 165, FL(46), WHITE)
    else:
        draw_ar_center(draw, formula, HEADER_H + 165, FA(34), WHITE)

    if c.get("example"):
        card(draw, 220, HEADER_H + 255, W - 220, HEADER_H + 330,
             fill=YELLOW_LIGHT, outline=YELLOW, r=14, lw=2)
        ex_lbl = ar("مثال")
        draw.text((W - 265, HEADER_H + 273), ex_lbl, font=FA(24), fill=YELLOW)
        example = c["example"]
        if c.get("formula_is_latin"):
            draw.text((235, HEADER_H + 271), example, font=FL(26), fill=YELLOW)
        else:
            t = ar(example)
            draw.text((W - 265 - tw(draw, t, FA(24)), HEADER_H + 271),
                      t, font=FA(24), fill=YELLOW)

    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


def slide_analysis(sub, items):
    img, _ = new_frame()
    add_header(img, "تحليل الخيارات", "نطبق المعيار على كل خيار")
    draw   = ImageDraw.Draw(img)

    y = HEADER_H + 12
    for item in items:
        correct = item["correct"]
        bg      = GREEN_LIGHT if correct else CARD_WHITE
        border  = GREEN       if correct else BORDER
        card(draw, 50, y, W - 50, y + 78, fill=bg, outline=border,
             r=12, lw=2 if correct else 1)

        display = item["display"]
        if item.get("display_is_latin"):
            fw = tw(draw, display, FL(27))
            draw.rounded_rectangle([68, y + 17, 68 + fw + 22, y + 59],
                                    radius=10, fill=GREEN if correct else RED)
            draw.text((79, y + 20), display, font=FL(27), fill=WHITE)
            reason_x = fw + 110
        else:
            t  = ar(display)
            fw = tw(draw, t, FA(24))
            draw.rounded_rectangle([W - 90 - fw - 12, y + 17, W - 78, y + 59],
                                    radius=10, fill=GREEN if correct else RED)
            draw.text((W - 90 - fw, y + 20), t, font=FA(24), fill=WHITE)
            reason_x = 68

        rt = ar(item["reason"])
        draw.text((reason_x, y + 24), rt, font=FA(22),
                  fill=GREEN_TEXT if correct else RED)
        y += 92

    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


def slide_answer(sub, s5, lesson):
    img, _ = new_frame()
    add_header(img, "الاجابة الصحيحة", lesson)
    draw   = ImageDraw.Draw(img)

    sg = make_gradient(W - 100, 185, (17, 130, 120), (30, 180, 80))
    img.paste(sg, (50, HEADER_H + 35))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([50, HEADER_H + 35, W - 50, HEADER_H + 220],
                            radius=20, outline=GREEN, width=3)

    ans = s5.get("answer_display", "")
    if s5.get("answer_is_latin"):
        fbw = tw(draw, ans, FL(82))
        draw.text(((W - fbw) // 2, HEADER_H + 42), ans, font=FL(82), fill=WHITE)
    else:
        draw_ar_center(draw, ans, HEADER_H + 55, FA(60), WHITE)

    if s5.get("answer_name"):
        name = s5["answer_name"]
        if s5.get("answer_is_latin"):
            draw_ar_center(draw, name, HEADER_H + 175, FL(30), WHITE)
        else:
            draw_ar_center(draw, name, HEADER_H + 175, FA(28), WHITE)

    card(draw, 110, HEADER_H + 232, W - 110, HEADER_H + 340,
         fill=YELLOW_LIGHT, outline=YELLOW, r=16, lw=2)
    if s5.get("answer_calc"):
        calc = s5["answer_calc"]
        if s5.get("answer_calc_is_latin"):
            draw_lat_center(draw, calc, HEADER_H + 246, FL(34), YELLOW)
        else:
            draw_ar_center(draw, calc, HEADER_H + 246, FA(28), YELLOW)
    if s5.get("answer_confirm"):
        draw_ar_center(draw, s5["answer_confirm"], HEADER_H + 295, FA(27), TEXT_DARK)

    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


def slide_explanation(sub, explanation_text):
    img, _ = new_frame()
    add_header(img, "الخلاصة والشرح", "")
    draw   = ImageDraw.Draw(img)

    sg = make_gradient(W - 100, 230, (37, 99, 235), (78, 205, 196))
    img.paste(sg, (50, HEADER_H + 20))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([50, HEADER_H + 20, W - 50, HEADER_H + 250],
                            radius=18, outline=BLUE, width=2)

    # نجمة بدل الإيموجي (متوافق مع الخطوط العادية)
    star = ar("★")
    draw.text(((W - tw(draw, star, FA(44))) // 2, HEADER_H + 28),
              star, font=FA(44), fill=WHITE)

    words = explanation_text.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if tw(draw, ar(" ".join(line)), FA(26)) > W - 160:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))

    y = HEADER_H + 90
    for ln in lines[:4]:
        draw_ar_center(draw, ln, y, FA(26), WHITE)
        y += 46

    add_subtitle_bar(img, sub)
    add_footer(img)
    return img


# ============================================================
# الصوت (ElevenLabs)
# ============================================================

def tts(text: str, path_mp3: str, api_key: str):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": api_key,
                 "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        json={"text": text,
              "model_id": "eleven_multilingual_v2",
              "voice_settings": {
                  "stability": 0.75, "similarity_boost": 0.90,
                  "speed": 0.82, "style": 0.0, "use_speaker_boost": True
              },
              "seed": 42},
        timeout=60
    )
    if r.status_code != 200:
        raise Exception(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    with open(path_mp3, "wb") as f:
        f.write(r.content)


# ============================================================
# توليد المحتوى بـ Gemini
# ============================================================

def generate_all_content(question_text, options, lesson, unit,
                         explanation=None, gemini_api_key=None) -> dict:
    from google import genai

    opts_lines = "\n".join(
        f"- {l}: {t}  {'(الإجابة الصحيحة)' if c else ''}"
        for l, t, c in options
    )

    prompt = f"""أنت مساعد تعليمي لمادة الكيمياء الثانوية.
أنشئ محتوى فيديو شرح للسؤال أدناه. أجب بـ JSON فقط بدون أي نص خارجه.

السؤال: {question_text}
الخيارات:
{opts_lines}
الوحدة: {unit}
الدرس: {lesson}
{'الشرح المتوفر: ' + explanation if explanation else ''}

أنشئ JSON بهذا الهيكل بالضبط:
{{
  "slide3": {{
    "title": "عنوان المفهوم/التعريف (قصير)",
    "line1": "وصف أول",
    "line2": "وصف ثانٍ (اختياري، أو اتركه فارغاً)",
    "formula": "الصيغة أو القاعدة (كيميائية أو عربية)",
    "formula_is_latin": true,
    "example": "مثال توضيحي مختصر (اختياري)"
  }},
  "slide4_items": [
    {{"display": "نص الخيار", "display_is_latin": true, "reason": "سبب الصح/الخطأ", "correct": false}},
    {{"display": "...", "display_is_latin": true, "reason": "...", "correct": false}},
    {{"display": "...", "display_is_latin": true, "reason": "...", "correct": true}},
    {{"display": "...", "display_is_latin": true, "reason": "...", "correct": false}}
  ],
  "slide5": {{
    "answer_display": "نص الإجابة الصحيحة",
    "answer_is_latin": true,
    "answer_name": "اسم المركب أو الإجابة بالعربية",
    "answer_calc": "الحساب أو التفسير المختصر",
    "answer_calc_is_latin": false,
    "answer_confirm": "جملة تأكيد قصيرة جداً"
  }},
  "explanation": "شرح مختصر 2-3 جمل بالعربية الفصحى البسيطة",
  "audios": [
    "نص صوت شريحة 1 - العنوان: تقديم الوحدة والدرس",
    "نص صوت شريحة 2 - السؤال: ما الذي يسأل السؤال؟",
    "نص صوت شريحة 3 - التعريف: اشرح المفهوم أو القاعدة",
    "نص صوت شريحة 4 - التحليل: طبّق على كل خيار",
    "نص صوت شريحة 5 - الإجابة: كشف الإجابة الصحيحة",
    "نص صوت شريحة 6 - الشرح: الخلاصة والدرس المستفاد"
  ],
  "subs": [
    "subtitle 1 (أقل من 55 حرف)",
    "subtitle 2",
    "subtitle 3",
    "subtitle 4",
    "subtitle 5",
    "subtitle 6"
  ]
}}

قواعد مهمة:
- formula_is_latin: true إذا كانت صيغة كيميائية/رياضية، false إذا عربية
- display_is_latin: true إذا كان الخيار صيغة كيميائية، false إذا نص عربي
- استخدم Unicode subscripts للأرقام الكيميائية: ₂=\\u2082 ₃=\\u2083 ₄=\\u2084 ₆=\\u2086
- النصوص الصوتية سلسة للاستماع، بدون تمهيد أو ترحيب مطوّل
- الـ subtitles قصيرة جداً (للقراءة السريعة)
- إذا ما في صيغة كيميائية، اكتب القاعدة أو التعريف بالعربية وضع formula_is_latin: false
"""

    try:
        from src.models.ai_analysis import AISetting
        _model = AISetting.get_setting('explanation_ai_model', 'gemini-2.0-flash')
    except Exception:
        _model = 'gemini-2.0-flash'
    try:
        from src.services.gemini_client import gemini_key_manager
        client = gemini_key_manager.get_client()
    except Exception:
        gemini_key_manager = None
        client = genai.Client(api_key=gemini_api_key)
    try:
        response = client.models.generate_content(
            model=_model, contents=prompt
        )
    except Exception as e:
        if gemini_key_manager and gemini_key_manager.is_quota_error(str(e)) and gemini_key_manager.rotate_key():
            client = gemini_key_manager.get_client()
            response = client.models.generate_content(
                model=_model, contents=prompt
            )
        else:
            raise
    text     = response.text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        text  = parts[1] if len(parts) > 1 else text
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# ============================================================
# الدالة الرئيسية — تقبل بيانات السؤال مباشرة من Flask ORM
# ============================================================

def generate_video(question_id: int, question_data: dict,
                   gemini_api_key: str, elevenlabs_api_key: str) -> str:
    """
    question_data: {
        'question_text': str,
        'explanation': str | None,
        'video_explanation': str | None,
        'lesson': str,
        'unit': str,
        'options': [(letter, text, is_correct), ...]
    }
    يُرجع مسار ملف MP4 في /tmp
    """
    # نستخدم video_explanation (المفصّل) إن وُجد، وإلا explanation
    explanation_for_video = (question_data.get('video_explanation')
                             or question_data.get('explanation'))

    content = generate_all_content(
        question_data['question_text'],
        question_data['options'],
        question_data['lesson'],
        question_data['unit'],
        explanation=explanation_for_video,
        gemini_api_key=gemini_api_key,
    )

    audios = content['audios']
    subs   = content['subs']
    data   = question_data

    slide_fns = [
        lambda sub: slide_title(sub, data['unit'], data['lesson']),
        lambda sub: slide_question(sub, data['question_text'], data['options'],
                                   data['unit'], data['lesson']),
        lambda sub: slide_formula(sub, content['slide3'], data['lesson']),
        lambda sub: slide_analysis(sub, content['slide4_items']),
        lambda sub: slide_answer(sub, content['slide5'], data['lesson']),
        lambda sub: slide_explanation(sub, content['explanation']),
    ]

    output = f"/tmp/question_{question_id}.mp4"
    tmp    = tempfile.mkdtemp()
    clips  = []

    for i, (fn, narration, sub) in enumerate(zip(slide_fns, audios, subs)):
        audio_path = os.path.join(tmp, f"audio_{i}.mp3")
        tts(narration, audio_path, elevenlabs_api_key)
        audio_clip = AudioFileClip(audio_path)

        img  = fn(sub)
        path = os.path.join(tmp, f"slide_{i}.png")
        img.save(path)

        clips.append(
            ImageClip(path)
            .with_duration(audio_clip.duration)
            .with_audio(audio_clip)
        )

    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(output, fps=FPS, codec="libx264",
                          audio_codec="aac", logger=None)
    return output
