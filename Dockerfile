FROM python:3.11-slim

# مكتبات WeasyPrint + Playwright/Chromium
RUN apt-get update && apt-get install -y \
    fonts-noto-color-emoji \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت Chromium لـ Playwright
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 10000

CMD gunicorn -c src/gunicorn.conf.py --timeout 300 --workers 2 --bind 0.0.0.0:$PORT src.main:app --access-logfile - --error-logfile - --capture-output --log-level info
