import os
from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import re

app = Flask(__name__)

# کلیدواژه‌ها برای استخراج اطلاعات
beneficiary_keywords = ["ذینفع", "مشتری", "گیرنده"]
total_keywords = ["جمع", "مبلغ کل", "Total", "Amount"]
currency_keywords = ["ریال", "دلار", "USD", "EUR"]
bank_keywords = ["بانک", "شماره حساب", "Account"]

# مقدار مهر شرکت برای مقایسه اسم ذینفع
COMPANY_SEAL_NAME = "شرکت نمونه"

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

        # استخراج متن با PyMuPDF
        doc = fitz.open(temp_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        os.remove(temp_path)

        lines = text.split("\n")

        # --- استخراج اسم ذینفع ---
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line:
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        beneficiary = lines[i + 1].strip()
                    else:
                        beneficiary = line.split(kw,1)[-1].strip(": -")
                    break
            if beneficiary != "Not found":
                break

        # بررسی مغایرت با مهر شرکت
        discrepancy = beneficiary != COMPANY_SEAL_NAME

        # --- استخراج جمع کل ---
        total_amount = None
        currency = None
        for line in lines:
            if any(kw in line for kw in total_keywords):
                # عدد و ارز
                amount_match = re.search(r"([\d,\.]+)", line)
                currency_match = re.search(r"(ریال|دلار|USD|EUR)", line)
                if amount_match:
                    total_amount = amount_match.group(1)
                if currency_match:
                    currency = currency_match.group(1)
                break

        # --- استخراج بانک و شماره حساب ---
        bank_name = None
        account_number = None
        for line in lines:
            if any(kw in line for kw in bank_keywords):
                bank_name_match = re.search(r"(بانک\s*[:\-]?\s*.+?)\s*(?:شماره|Account|$)", line)
                account_match = re.search(r"(?:شماره\s*حساب|Account)\s*[:\-]?\s*([\d\-]+)", line)
                if bank_name_match:
                    bank_name = bank_name_match.group(1).strip()
                if account_match:
                    account_number = account_match.group(1).strip()
                if bank_name or account_number:
                    break

        return jsonify({
            "filename": file.filename,
            "beneficiary": beneficiary,
            "discrepancy_with_seal": discrepancy,
            "total_amount": total_amount,
            "currency": currency,
            "bank_name": bank_name,
            "account_number": account_number
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)