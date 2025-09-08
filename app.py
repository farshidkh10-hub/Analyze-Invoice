@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    file = request.files.get("file")
    if not file:
        return {"error": "No file uploaded"}, 400

    try:
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        # خواندن متن PDF
        doc = fitz.open(temp_path)
        text = "".join([page.get_text("text") + "\n" for page in doc])
        doc.close()
        os.remove(temp_path)

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # --- Beneficiary ---
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line.lower():
                    parts = re.split(r"[:\-]", line, maxsplit=1)
                    if len(parts) > 1 and parts[1].strip():
                        beneficiary = parts[1].strip()
                    elif i + 1 < len(lines):
                        beneficiary = lines[i + 1].strip()
                    break
            if beneficiary != "Not found":
                break

        # fallback: جستجو در کل متن اگر هنوز پیدا نشده
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
                amounts = re.findall(r"([\d,]+\.\d+|[\d,]+)", line)
                currencies = re.findall(r"\b(usd|eur|jpy|gbp)\b", line, re.IGNORECASE)
                if amounts:
                    total_amount = max([float(a.replace(",", "")) for a in amounts])
                    total_amount = str(total_amount)
                if currencies:
                    currency = currencies[0].upper()
                break

        # fallback: جستجو در کل متن برای عدد بزرگ و واحد ارز
        if not total_amount:
            all_amounts = re.findall(r"([\d,]+\.\d+|[\d,]+)", text)
            if all_amounts:
                total_amount = str(max([float(a.replace(",", "")) for a in all_amounts]))
            cur_match = re.search(r"\b(usd|eur|jpy|gbp)\b", text, re.IGNORECASE)
            if cur_match:
                currency = cur_match.group(1).upper()

        # --- Banking Information پیشرفته ---
        bank_name = "Not found"
        bank_address = "Not found"
        swift_code = "Not found"
        account_number = "Not found"

        # جستجو در خطوط برای بانک
        for i, line in enumerate(lines):
            l = line.strip()
            l_lower = l.lower()

            # نام بانک: شامل 'bank' یا 'bank name' باشد
            if ("bank" in l_lower and bank_name == "Not found") or ("bank name" in l_lower):
                bank_name = l.split(":",1)[-1].strip() if ":" in l else l.strip()

            # آدرس بانک
            elif ("address" in l_lower and bank_address == "Not found") or ("bank address" in l_lower):
                bank_address = l.split(":",1)[-1].strip() if ":" in l else l.strip()

            # Swift Code
            if ("swift" in l_lower and swift_code == "Not found"):
                match = re.search(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b", l)
                if match:
                    swift_code = match.group(0)
                else:
                    swift_code = l.split(":",1)[-1].strip() if ":" in l else l.strip()

            # Account Number
            if (("account" in l_lower or "a/c" in l_lower) and account_number == "Not found"):
                match = re.search(r"\d{6,}", l.replace(" ", ""))
                if match:
                    account_number = match.group(0)
                else:
                    account_number = l.split(":",1)[-1].strip() if ":" in l else l.strip()

        # fallback: اگر هنوز چیزی پیدا نشده، regex روی کل متن
        if bank_name == "Not found":
            bank_match = re.search(r"Bank\s*[:\-]?\s*(\w[\w\s&]+)", text, re.IGNORECASE)
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

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "total_amount": total_amount,
            "currency": currency,
            "bank_name": bank_name,
            "bank_address": bank_address,
            "swift_code": swift_code,
            "account_number": account_number
        }

    except Exception as e:
        return {"error": str(e)}, 500