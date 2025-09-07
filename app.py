import os
from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import re
from fuzzywuzzy import fuzz

app = Flask(__name__)

# کلیدواژه‌ها و نام شرکت برای مقایسه
beneficiary_keywords = ["Beneficiary", "Customer", "SELLER"]
total_keywords = ["TOTAL AMOUNT", "AMOUNT"]
currency_keywords = ["DOLLAR", "EURO", "DIRHAM", "RPM"]
bank_keywords = ["Bank Name","A/C No.", "Account Number"]
COMPANY_SEAL_NAME = "Example Company"

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Analyze Invoice</title>
<style>
body { font-family: Arial, sans-serif; padding: 20px; }
table { border-collapse: collapse; width: 80%; margin-top: 20px; }
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
        html += `<tr><td>Beneficiary</td><td>${data.beneficiary}</td></tr>`;
        html += `<tr><td>Discrepancy with Company</td><td>${data.discrepancy_with_seal ? 'Yes' : 'No'}</td></tr>`;
        html += `<tr><td>Similarity Percentage</td><td>${data.similarity_percentage}%</td></tr>`;
        html += `<tr><td>Total Amount</td><td>${data.total_amount || '-'}</td></tr>`;
        html += `<tr><td>Currency</td><td>${data.currency || '-'}</td></tr>`;
        html += `<tr><td>Bank Name</td><td>${data.bank_name || '-'}</td></tr>`;
        html += `<tr><td>Account Number</td><td>${data.account_number || '-'}</td></tr>`;
        html += '</table>';
        document.getElementById('result').innerHTML = html;
    })
    .catch(err => { document.getElementById('result').innerHTML = '<p style="color:red;">Error: '+err+'</p>'; });
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

        # استخراج متن PDF
        doc = fitz.open(temp_path)
        text = "".join([page.get_text("text") + "\n" for page in doc])
        doc.close()
        os.remove(temp_path)

        lines = text.split("\n")

        # --- Beneficiary ---
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line:
                    parts = line.split(kw)
                    if len(parts) > 1 and parts[1].strip():
                        beneficiary = parts[1].strip(": - ")
                    elif i+1 < len(lines):
                        beneficiary = lines[i+1].strip()
                    break
            if beneficiary != "Not found": break

        similarity = fuzz.token_sort_ratio(beneficiary, COMPANY_SEAL_NAME)
        discrepancy = similarity < 90

        # --- Total Amount & Currency ---
        total_amount = None
        currency = None
        for line in lines:
            if any(kw in line for kw in total_keywords):
                amt = re.search(r"([\d,\.]+)", line)
                cur = re.search(r"(" + "|".join(currency_keywords) + ")", line)
                if amt: total_amount = amt.group(1).replace(",", "")
                if cur: currency = cur.group(1)
                break

        # --- Bank & Account Number ---
        bank_name = None
        account_number = None
        for line in lines:
            if any(kw in line for kw in bank_keywords):
                bn = re.search(r"(?:Bank\s*[:\-]?\s*)(.+?)(?:Account|$)", line, re.IGNORECASE)
                ac = re.search(r"(?:Account\s*Number\s*[:\-]?\s*)([\d\-]+)", line, re.IGNORECASE)
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