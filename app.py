import os
import re
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
import pytesseract
from pytesseract import Output
from rapidfuzz import fuzz

app = Flask(__name__)

# ----------------------------
# کلیدواژه‌ها و regex
# ----------------------------
keywords = {
    "beneficiary_name": [r"beneficiary['’]?s name[:\s]*([^\n]+)", r"نام ذینفع[:\s]*([^\n]+)"],
    "bank": [r"bank[:\s]*([^\n]+)", r"نام بانک[:\s]*([^\n]+)", r"banking information[:\s]*([^\n]+)"],
    "bank_address": [r"bank address[:\s]*([^\n]+)", r"آدرس بانک[:\s]*([^\n]+)"],
    "account_no": [r"a/c no[:\s]*([^\n]+)", r"account number[:\s]*([^\n]+)", r"شماره حساب[:\s]*([^\n]+)"],
    "swift": [r"swift code[:\s]*([^\n]+)", r"swift[:\s]*([^\n]+)", r"سوییفت کد[:\s]*([^\n]+)"],
    "currency": [r"currency[:\s]*([^\n]+)", r"نوع ارز[:\s]*([^\n]+)"],
    "amount": [r"total[:\s]*([^\n]+)", r"amount[:\s]*([^\n]+)", r"جمع ارز[:\s]*([^\n]+)"],
}

MATCH_THRESHOLD = 70
MAX_PART_LENGTH = 100
LOG_DIR = "./pdf_logs"
JSON_DIR = "./pdf_json"
TEMP_DIR = "./temp_pages"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ----------------------------
# تقسیم PDF به صفحات جداگانه
# ----------------------------
def split_pdf_to_pages(pdf_path):
    reader = PdfReader(pdf_path)
    page_files = []
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        page_file = os.path.join(TEMP_DIR, f"page_{i+1}.pdf")
        with open(page_file, "wb") as f:
            writer.write(f)
        page_files.append(page_file)
    return page_files

# ----------------------------
# استخراج متن OCR از یک صفحه PDF
# ----------------------------
def extract_text_from_pdf_page(page_pdf_path):
    images = convert_from_path(page_pdf_path)
    blocks = []
    for img in images:
        text = pytesseract.image_to_string(img, lang="fas+eng", output_type=Output.STRING)
        if text.strip():
            blocks.append(text)
    return blocks

# ----------------------------
# استخراج فیلد با regex و fallback fuzzy
# ----------------------------
def extract_field(blocks, regex_list):
    for block in blocks:
        for pattern in regex_list:
            m = re.search(pattern, block, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip(), 100
    for block in blocks:
        for i in range(0, len(block), MAX_PART_LENGTH):
            part = block[i:i+MAX_PART_LENGTH]
            for pattern in regex_list:
                key_text = re.sub(r"[:\s]*", "", pattern)[:20]
                ratio = fuzz.partial_ratio(part.lower(), key_text.lower())
                if ratio >= MATCH_THRESHOLD:
                    return part.strip(), ratio
    return "یافت نشد", 0

# ----------------------------
# پردازش PDF در پس‌زمینه
# ----------------------------
def process_pdf_background(pdf_path, output_filename):
    try:
        page_files = split_pdf_to_pages(pdf_path)
        all_blocks = []
        for page_file in page_files:
            blocks = extract_text_from_pdf_page(page_file)
            all_blocks.extend(blocks)

        results = {}
        problem_flag = False
        for field, regex_list in keywords.items():
            value, confidence = extract_field(all_blocks, regex_list)
            results[field] = {"value": value, "confidence": f"{confidence}%"}
            if value == "یافت نشد" or confidence < MATCH_THRESHOLD:
                problem_flag = True

        json_filename = os.path.join(JSON_DIR, output_filename)
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        if problem_flag:
            log_filename = os.path.join(LOG_DIR, "problem_files.log")
            with open(log_filename, "a", encoding="utf-8") as logf:
                logf.write(f"{output_filename} - {datetime.now().isoformat()}\n")
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")

# ----------------------------
# مسیر آپلود PDF
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def upload_pdf():
    if request.method == "POST":
        file = request.files.get("pdf_file")
        if not file:
            return "فایلی ارسال نشده"

        pdf_path = os.path.join(TEMP_DIR, file.filename)
        file.save(pdf_path)

        output_filename = f"{file.filename}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"

        # شروع پردازش در پس‌زمینه
        thread = threading.Thread(target=process_pdf_background, args=(pdf_path, output_filename))
        thread.start()

        return f'''
        <h3>PDF دریافت شد و پردازش در حال انجام است.</h3>
        <p>بعد از اتمام، فایل JSON زیر آماده می‌شود:</p>
        <p>{output_filename}</p>
        <p>می‌توانید این فایل را بعداً بررسی کنید.</p>
        '''

    return '''
    <h2>آپلود PDF</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="pdf_file">
        <input type="submit" value="بررسی PDF">
    </form>
    '''

if __name__ == "__main__":
    app.run(debug=True)