import os
from flask import Flask, request, jsonify, render_template_string
import fitz  # PyMuPDF
import re
from fuzzywuzzy import fuzz

app = Flask(__name__)

# کلیدواژه‌ها و مقدار مهر شرکت
beneficiary_keywords = ["ذینفع", "مشتری", "گیرنده"]
total_keywords = ["جمع", "مبلغ کل", "Total", "Amount"]
currency_keywords = ["ریال", "دلار", "USD", "EUR"]
bank_keywords = ["بانک", "شماره حساب", "Account"]
COMPANY_SEAL_NAME = "شرکت نمونه"

# صفحه وب ساده برای آپلود فایل
HTML_PAGE = """
<!DOCTYPE html>
<html lang="fa">
<head>
<meta charset="UTF-8">
<title>Analyze Invoice</title>
</head>
<body>
<h2>آپلود فاکتور PDF و بررسی</h2>
<input type="file" id="fileInput" accept="application/pdf">
<button onclick="uploadFile()">بررسی</button>
<pre id="result"></pre>

<script>
function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if(fileInput.files.length === 0) {
        alert('یک فایل انتخاب کنید!');
        return;
    }
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/analyze', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('result').textContent = JSON.stringify(data, null, 2);
    })
    .catch(err => {
        document.getElementById('result').textContent = 'خطا: ' + err;
    });
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        doc = fitz.open(temp_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        os.remove(temp_path)

        lines = text.split("\n")

        # استخراج اسم ذینفع
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line:
                    if i+1 < len(lines) and lines[i+1].strip():
                        beneficiary = lines[i+1].strip()
                    else:
                        beneficiary = line.split(kw,1)[-1].strip(": -")
                    break
            if beneficiary != "Not found":
                break

        similarity = fuzz.token_sort_ratio(beneficiary, COMPANY_SEAL_NAME)
        discrepancy = similarity < 90

        # جمع کل و ارز
        total_amount = None
        currency = None
        for line in lines:
            if any(kw in line for kw in total_keywords):
                amt = re.search(r"([\d,\.]+)", line)
                cur = re.search(r"(ریال|دلار|USD|EUR)", line)
                if amt: total_amount = amt.group(1).replace(",", "")
                if cur: currency = cur.group(1)
                break

        # بانک و شماره حساب
        bank_name = None
        account_number = None
        for line in lines:
            if any(kw in line for kw in bank_keywords):
                bn = re.search(r"(?:بانک\s*[:\-]?\s*|Bank\s*[:\-]?\s*)(.+?)(?:\s+شماره|Account|$)", line, re.IGNORECASE)
                ac = re.search(r"(?:شماره\s*حساب|Account)\s*[:\-]?\s*([\d\-]+)", line, re.IGNORECASE)
                if bn: bank_name = bn.group(1).strip()
                if ac: account_number = ac.group(1).strip()
                if bank_name or account_number:
                    break

        return jsonify({
            "filename": file.filename,
            "beneficiary": beneficiary,
            "discrepancy_with_seal": discrepancy,
            "similarity_percentage": similarity,
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