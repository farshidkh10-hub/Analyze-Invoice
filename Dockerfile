FROM python:3.10-slim

# نصب ابزارهای مورد نیاز برای OCR و PDF
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# محل اجرای برنامه
WORKDIR /app

# نصب پکیج‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل سورس
COPY . .

# اجرای اپ با gunicorn (پورت 10000 برای Render)
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]