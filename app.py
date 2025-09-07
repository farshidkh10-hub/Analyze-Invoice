import os
from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import re
from fuzzywuzzy import fuzz

app = Flask(__name__)

# کلیدواژه‌ها و مهر شرکت
beneficiary_keywords = ["ذینفع", "مشتری", "گیرنده"]
total_keywords = ["جمع", "مبلغ کل", "Total", "Amount"]
currency_keywords = ["ریال", "دلار", "USD", "EUR"]
bank_keywords = ["بانک", "شماره حساب", "Account"]
COMPANY_SEAL_NAME = "شرکت نمونه"

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fa">
<head>
<meta charset="UTF-8">
<title>Analyze Invoice</title>
<style>
body { font-family: Tahoma, sans-serif; direction: rtl; padding: 20px; }
table { border-collapse: collapse; width: 80%; margin-top: 20px; }
th, td { border: 1px solid #333; padding: 8px; text-align: right; }
th { background-color: #f2f2f2; }
</style>
</head>
<body>
<h2>آپلود فاکتور PDF و بررسی</h2>
<input type="file" id="fileInput" accept="application/pdf">
<button onclick="uploadFile()">بررسی</button>
<div id="result"></div>

<script>
function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if(fileInput.files.length === 0) { alert('یک فایل انتخاب کنید!'); return; }
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
        html += '<tr><th>فیلد</th><th>مقدار</th></tr>';
        html += `<tr><td>نام فایل</td><td>${data.filename}</td></tr>`;
        html += `<tr><td>ذینفع</td><td>${data.beneficiary}</td></tr>`;
        html += `<tr><td>مغایرت با مهر شرکت</td><td>${data.discrepancy_with_seal ? 'بله' : 'خیر'}</td></tr>`;
        html += `<tr><td>درصد شباهت</td><td>${data.similarity_percentage}%</td></tr>`;
        html += `<tr><td>جمع کل</td><td>${data.total_amount || '-'}</td></tr>`;
        html += `<tr><td>ارز</td><td>${data.currency || '-'}</td></tr>`;
        html += `<tr><td>نام بانک</td><td>${data.bank_name || '-'}</td></tr>`;
        html += `<tr><td>شماره حساب</td><td>${data.account_number || '-'}</td></tr>`;
        html += '</table>';
        document.getElementById('result').innerHTML = html;
    })
    .catch(err => { document.getElementById('result').innerHTML = '<p style="color:red;">خطا: '+err+'</p>'; });
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
        return {"error": "No file uploaded"}, 400

    try:
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        doc = fitz.open(temp_path)
        text = "".join([page.get_text("text") + "\n" for page in doc])
        doc.close()
        os.remove(temp_path)

        lines = text.split("\n")

        # استخراج ذینفع
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line:
                    if i+1 < len(lines) and lines[i+1].strip():
                        beneficiary = lines[i+1].strip()
                    else:
                        beneficiary = line.split(kw,1)[-1].strip(": -")
                    break
            if beneficiary != "Not found": break

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
                if bank_name or account_number: break

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "discrepancy_with_seal": discrepancy,
            "similarity_percentage": similarity,
            "total_amount": total_amount,
            "currency": currency,
            "bank_name": bank_name,
            "account_number": account_number
        }

    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)