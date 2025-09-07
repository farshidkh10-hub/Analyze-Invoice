import os
from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import re

app = Flask(__name__)

@app.route("/")
def home():
    return "Analyze Invoice API is running ✅"

@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # ذخیره موقت فایل PDF
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        # باز کردن PDF با PyMuPDF
        doc = fitz.open(temp_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        os.remove(temp_path)  # پاک کردن فایل موقت

        # استخراج اسم ذینفع با Regex ساده
        # اینجا می‌تونی الگوی دقیق فاکتور خودت رو جایگزین کنی
        match = re.search(r"(?:Beneficiary|ذینفع|مشتری|Company|Customer)[:\-]?\s*(.+)", text, re.IGNORECASE)
        beneficiary = match.group(1).strip() if match else "Not found"

        return jsonify({
            "filename": file.filename,
            "beneficiary": beneficiary
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)