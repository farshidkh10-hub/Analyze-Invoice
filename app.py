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

# ----------------------------
# Mapping ارزها به فرمت استاندارد
# ----------------------------
currencies_map = {
    "CNY": "CNY",
    "Dollar": "USD",
    "USD": "USD",
    "EURO": "EUR",
    "AED": "AED",
    "DIRHAM": "AED"
}

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
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Analyze Invoice</title>
<style>
body { font-family: Arial, sans-serif; padding: 20px; }
table { border-collapse: collapse; width: 90%; margin-top: 20px; }
th, td { border: 1px solid #333; padding: 8px; text-align: left; }
th { background-color: #f2f2f2; }
</style>
</head>
<body>
<h2>Upload PDF Invoice and Analyze</h2>
<input type="file" id="fileInput" accept="application/pdf">
<button onclick="uploadFile()">Analyze</button>
<div id="result"></div>

<script>
function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if(fileInput.files.length === 0) { alert('Please select a file!'); return; }
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/analyze', { method: 'POST', body: formData })
    .then(response => response.json())
    .then(data => {
        if(data.error) {
            document.getElementById('result').innerHTML = '<p style="color:red;">' + data.error + '</p>';
            return;
        }
        let html = '<table>';
        html += '<tr><th>Field</th><th>Value</th></tr>';
        html += `<tr><td>File Name</td><td>${data.filename}</td></tr>`;
        html += `<tr><td>Beneficiary Name</td><td>${data.beneficiary}</td></tr>`;
        html += `<tr><td>Currency</td><td>${data.currency || '-'}</td></tr>`;
        html += `<tr><td>Bank Name</td><td>${data.bank_name || '-'}</td></tr>`;
        html += `<tr><td>Bank Address</td><td>${data.bank_address || '-'}</td></tr>`;
        html += `<tr><td>Swift Code</td><td>${data.swift_code || '-'}</td></tr>`;
        html += `<tr><td>Account Number</td><td>${data.account_number || '-'}</td></tr>`;
        html += `<tr><td>Verification Status</td><td>${data.verification_status}</td></tr>`;
        html += '</table>';
        document.getElementById('result').innerHTML = html;
    })
    .catch(err => { document.getElementById('result').innerHTML = '<p style="color:red;">Error: '+err+'</p>'; });
}
</script>
</body>
</html>
"""

# ----------------------------
# تابع امن برای استخراج نام بانک
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
        # --- خواندن PDF مستقیم از حافظه ---
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

        # --- Currency ---
        currency = None
        for c in currencies_map.keys():
            if c.lower() in text.lower():
                currency = currencies_map[c]
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

        bank_name_std = sanitize_bank_name(bank_name)

        # --- Verification ---
        verification_status = "تایید شده"

        # شرط 1: اگر ارز USD است و بانک شامل China نیست
        if currency == "USD" and "CHINA" not in bank_name_std:
            verification_status = "تایید نشده"

        # شرط 2: اگر اسم بانک در لیست حساس است
        for b in suspicious_banks:
            if b.upper() in bank_name_std:
                verification_status = "تایید نشده"
                break

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "currency": currency,
            "bank_name": bank_name,
            "bank_address": bank_address,
            "swift_code": swift_code,
            "account_number": account_number,
            "verification_status": verification_status
        }

    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)