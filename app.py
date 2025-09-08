import traceback

@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    file = request.files.get("file")
    if not file:
        return {"error": "No file uploaded"}, 400

    try:
        # --- خواندن PDF مستقیم از حافظه ---
        pdf_bytes = file.read()
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as pdf_err:
            return {"error": f"Cannot open PDF: {str(pdf_err)}"}, 400

        try:
            text = "".join([page.get_text("text") + "\n" for page in doc])
        except Exception as text_err:
            doc.close()
            return {"error": f"Cannot extract text from PDF: {str(text_err)}"}, 400

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

        # --- Currency ---
        currency = None
        text_lower = text.lower()
        for key, std in currencies_map.items():
            if key.lower() in text_lower:
                currency = std
                break

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
                swift_code = l.split(":",1)[-1].strip() if ":" in l else l.strip()
            if (("account" in l_lower or "a/c" in l_lower) and account_number == "Not found"):
                account_number = l.split(":",1)[-1].strip() if ":" in l else l.strip()

        # --- استانداردسازی نام بانک ---
        bank_name_std = sanitize_bank_name(bank_name)

        # --- Verification ---
        verification_currency = "تایید شده"
        verification_bank = "تایید شده"

        # شرط 1: حواله دلاری خارج از چین
        if currency == "USD" and "CHINA" not in bank_name_std:
            verification_currency = "تایید نشده"

        # شرط 2: بانک‌های حساس
        for b in suspicious_banks:
            b_std = sanitize_bank_name(b)
            if b_std in bank_name_std:
                verification_bank = "تایید نشده"
                break

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "currency": currency,
            "bank_name": bank_name,
            "bank_address": bank_address,
            "swift_code": swift_code,
            "account_number": account_number,
            "verification_currency": verification_currency,
            "verification_bank": verification_bank
        }

    except Exception as e:
        # چاپ کامل Exception در لاگ سرور برای بررسی
        traceback.print_exc()
        return {"error": str(e)}, 500