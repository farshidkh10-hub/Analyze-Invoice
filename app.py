import os
from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import re
from fuzzywuzzy import fuzz

app = Flask(__name__)

# ----------------------------
# لیست کلیدواژه‌ها (همه به lowercase)
# ----------------------------
beneficiary_keywords = [
    "beneficiary's name",
    "beneficiary name",
    "seller",
    "company name"
]

bank_keywords = [
    "bank address",
    "address",
    "beneficiary’s bank",
    "bank information",
    "banking information",
    "bank",
    "add"
]

account_keywords = [
    "account no.",
    "account number",
    "a/c no",
    "account no"
]

total_keywords = [
    "total amount",
    "amount",
    "total",
    "cif value",
    "total value"
]

swift_keywords = [
    "swift",
    "swift code"
]

currency_keywords = ["usd", "eur", "jpy", "gbp"]

COMPANY_SEAL_NAME = "Example Company"

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
        html += `<tr><td>Discrepancy with Company</td><td>${data.discrepancy_with_seal ? 'Yes' : 'No'}</td></tr>`;
        html += `<tr><td>Similarity Percentage</td><td>${data.similarity_percentage}%</td></tr>`;
        html += `<tr><td>Total Amount</td><td>${data.total_amount || '-'}</td></tr>`;
        html += `<tr><td>Currency</td><td>${data.currency || '-'}</td></tr>`;
        html += `<tr><td>Bank Name</td><td>${data.bank_name || '-'}</td></tr>`;
        html += `<tr><td>Bank Address</td><td>${data.bank_address || '-'}</td></tr>`;
        html += `<tr><td>Swift Code</td><td>${data.swift_code || '-'}</td></tr>`;
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
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        doc = fitz.open(temp_path)
        text = "".join([page.get_text("text") + "\n" for page in doc])
        doc.close()
        os.remove(temp_path)

        lines = text.split("\n")

        # --- Beneficiary ---
        beneficiary = "Not found"
        for i, line in enumerate(lines):
            for kw in beneficiary_keywords:
                if kw in line.lower():
                    parts = re.split(r"[:\-]", line, maxsplit=1)
                    if len(parts) > 1 and parts[1].strip():
                        beneficiary = parts[1].strip()
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
            if any(kw in line.lower() for kw in total_keywords):
                amt = re.search(r"([\d,\.]+)", line)
                cur = re.search(r"(" + "|".join(currency_keywords) + ")", line.lower())
                if amt: total_amount = amt.group(1).replace(",", "")
                if cur: currency = cur.group(1).upper()
                break

        # --- Bank Name & Address ---
        bank_name = None
        bank_address = None
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in bank_keywords):
                if i+1 < len(lines):
                    bank_name = lines[i+1].strip()
                break

        bank_address = bank_name
        for i, line in enumerate(lines):
            if "address" in line.lower():
                bank_address = line.split(":")[-1].strip()
                break

        # --- Swift Code ---
        swift_code = None
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in swift_keywords):
                parts = re.split(r"[:\-]", line, maxsplit=1)
                if len(parts) > 1 and parts[1].strip():
                    swift_code = parts[1].strip()
                elif i+1 < len(lines):
                    swift_code = lines[i+1].strip()
                break

        # --- Account Number ---
        account_number = None
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in account_keywords):
                parts = re.split(r"[:\-]", line, maxsplit=1)
                if len(parts) > 1 and parts[1].strip():
                    account_number = parts[1].strip()
                elif i+1 < len(lines):
                    account_number = lines[i+1].strip()
                break

        return {
            "filename": file.filename,
            "beneficiary": beneficiary,
            "discrepancy_with_seal": discrepancy,
            "similarity_percentage": similarity,
            "total_amount": total_amount,
            "currency": currency,
            "bank_name": bank_name,
            "bank_address": bank_address,
            "swift_code": swift_code,
            "account_number": account_number
        }

    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)