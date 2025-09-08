import re
from flask import Flask, request, render_template_string
import fitz  # PyMuPDF

app = Flask(__name__)

# ----------------------------
# کلیدواژه‌ها (همه lowercase)
# ----------------------------
beneficiary_keywords = [
    "beneficiary's name",
    "beneficiary name",
    "seller",
    "company name"
]

total_keywords = [
    "total amount",
    "amount",
    "total",
    "cif value",
    "total value"
]

currency_keywords = ["usd", "eur", "jpy", "gbp"]

# ----------------------------
# لیست بانک‌های حساس
# ----------------------------
suspicious_banks = [
    "STANDARD CHARTERED",
    "DBS HONG KONG",
    "CITI BANK HONG KONG",
    "HSBC",
    "BANK OF CHINA",
    "CHASE BANK",
    "KUNLUN BANK",
    "UCO BANK",
    "CHOUZHOU",
    "JP MORGAN"
]

# ----------------------------
# HTML صفحه وب
# ----------------------------
HTML_PAGE = """ ... همان HTML صفحه قبلی ... """  # همون HTML که داری استفاده می‌کنی

# ----------------------------
# تابع امن برای تبدیل Amount به float
# ----------------------------
def parse_amount(s):
    s_clean = re.sub(r"[^0-9.,]", "", s)
    if s_clean == "":
        return None
    s_clean = s_clean.replace(",", "")
    try:
        return float(s_clean)
    except:
        return None

# ----------------------------
# تابع امن برای استانداردسازی نام بانک
# ----------------------------
def sanitize_bank_name(name):
    return re.sub(r"[^A-Za-z0-9\s]", "", name).upper().strip()

# ----------------------------
# Route ها
# ----------------------------
@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    file = request.files.get("file")
    if not file:
        return {"error": "No file uploaded"}, 400

    try:
        pdf_bytes = file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "".join([page.get_text("text") + "\n" for page in doc])
        doc.close()

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # --- Beneficiary ---
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        beneficiary = parts[1].strip()
                    elif i+1 < len(lines):
                        beneficiary = lines[i+1].strip()
                    break
            if beneficiary != "Not found":
                break
        if beneficiary == "Not found":
            for line in lines:
                if len(line.split()) <= 5 and line.isalpha():
                    beneficiary = line.strip()
                    break

        # --- Total Amount & Currency ---
        total_amount = None
        currency = None
        for line in lines:
            if any(kw in line.lower() for kw in total_keywords):
                amounts = [parse_amount(a) for a in re.findall(r"([\d,]+\.\d+|[\d,]+)", line)]
                amounts = [a for a in amounts if a is not None]
                currencies = re.findall(r"\b(usd|eur|jpy|gbp)\b", line, re.IGNORECASE)
                if amounts:
                    total_amount = str(max(amounts))
                if currencies:
                    currency = currencies[0].upper()
                break

        if not total_amount:
            all_amounts = [parse_amount(a) for a in re.findall(r"([\d,]+\.\d+|[\d,]+)", text)]
            all_amounts = [a for a in all_amounts if a is not None]
            if all_amounts:
                total_amount = str(max(all_amounts))
            cur_match = re.search(r"\b(usd|eur|jpy|gbp)\b", text, re.IGNORECASE)
            if cur_match:
                currency = cur_match.group(1).upper()

        # --- Banking Information ---
        bank_name = "Not found"
        bank_address = "Not found"
        swift_code = "Not found"
        account_number = "Not found"

        for i, line in enumerate(lines):
            l = line.strip()
            l_lower = l.lower()
            if (("bank" in l_lower or "bank name" in l_lower) and bank_name == "Not found"):
                bank_name = l.split(":",1)[-1].strip() if ":" in l else l.strip()
            elif ("address" in l_lower and bank_address == "Not found"):
                bank_address = l.split(":",1)[-1].strip() if ":" in l else l.strip()
            if ("swift" in l_lower and swift_code == "Not found"):
                match = re.search(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b", l)
                if match:
                    swift_code = match.group(0)
                else:
                    swift_code = l.split(":",1)[-1].strip() if ":" in l else l.strip()
            if (("account" in l_lower or "a/c" in l_lower) and account_number == "Not found"):
                match = re.search(r"\d{6,}", l.replace(" ", ""))
                if match:
                    account_number = match.group(0)
                else:
                    account_number = l.split(":",1)[-1].strip() if ":" in l else l.strip()

        # fallback روی کل متن
        if bank_name == "Not found":
            bank_match = re.search(r"Bank\s*[:\-]?\s*([\w\s&]+)", text, re.IGNORECASE)
            if bank_match:
                bank_name = bank_match.group(1).strip()
        if swift_code == "Not found":
            swift_match = re.search(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b", text)
            if swift_match:
                swift_code = swift_match.group(0)
        if account_number == "Not found":
            acc_match = re.search(r"\b\d{6,}\b", text.replace(" ", ""))
            if acc_match:
                account_number = acc_match.group(0)

        # --- Verification ---
        bank_name_std = sanitize_bank_name(bank_name)
        verification_currency = "تایید شده"
        verification_bank = "تایید شده"

        # ارز USD خارج از چین
        if currency == "USD" and "CHINA" not in bank_name_std:
            verification_currency = "تایید نشده"

        # بانک‌های حساس
        for b in suspicious_banks:
            if sanitize_bank_name(b) in bank_name_std:
                verification_bank = "تایید نشده"
                break

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "total_amount": total_amount,
            "currency": currency,
            "bank_name": bank_name,
            "bank_address": bank_address,
            "swift_code": swift_code,
            "account_number": account_number,
            "verification_currency": verification_currency,
            "verification_bank": verification_bank
        }

    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)