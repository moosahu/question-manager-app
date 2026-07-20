#!/usr/bin/env bash
set -e

pip install -r requirements.txt
playwright install chromium --with-deps

# تحقق فعلي إن Chromium نزل واشتغل فعلاً — بدون هذا التحقق، أي فشل صامت
# بتثبيت المتصفح (مثال حقيقي حصل: تعارض إصدار playwright مع نسخة Chromium
# المخزّنة بالـcache) يخلي التطبيق يرجع بصمت لـWeasyPrint (محرك احتياطي فيه
# علل حقيقية بترتيب RTL) لكل استخراج اختبار، بدون أي تنبيه بفشل الـdeploy.
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    browser.close()
print('Chromium OK')
"
