import re
from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
from fuzzywuzzy import fuzz
import tempfile

app = Flask(__name__)

# ----------------------------
# کلیدواژه‌ها
# ----------------------------
fields = {
    "beneficiary_name": ["beneficiary's name", "beneficiary name", "seller"],
    "bank_name": ["bank", "banking information"],
    "bank_address": ["bank address", "add"],
    "swift_code": ["swift code", "swift"],
    "currency_type": ["currency type", "type of currency", "currency"],
    "amount": ["total", "amount"],
    "account_number": ["a/c no", "account number"]
}

# ----------------------------
# تابع استخراج متن از PDF
# ----------------------------
def extract_text(file_storage):
    text = ""
    # فایل آپلودی رو موقت ذخیره می‌کنیم
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file_storage.save(tmp.name)
        doc = fitz.open(tmp.name)
        for page in doc:
            text += page.get_text()
        doc.close()
    return text

# ----------------------------
# تابع پیدا کردن مقدار با fuzzy match
# ----------------------------
def find_field_value(text, keywords):
    text_lines = text.splitlines()
    for idx, line in enumerate(text_lines):
        for keyword in keywords:
            if fuzz.partial_ratio(keyword.lower(), line.lower()) > 80:
                parts = re.split(r":|=", line)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
                elif idx + 1 < len(text_lines):
                    return text_lines[idx+1].strip()
    return "Not Found"

# ----------------------------
# مسیر اصلی Flask
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = {}
    if request.method == "POST":
        pdf_file = request.files.get("pdf_file")
        if pdf_file:
            text = extract_text(pdf_file)
            for field, keywords in fields.items():
                result[field] = find_field_value(text, keywords)

    html = """
    <h2>PDF Information Extractor</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="pdf_file" required>
        <input type="submit" value="Extract">
    </form>
    {% if result %}
        <h3>Extracted Data:</h3>
        <ul>
        {% for key, value in result.items() %}
            <li><b>{{ key.replace('_',' ').title() }}:</b> {{ value }}</li>
        {% endfor %}
        </ul>
    {% endif %}
    """
    return render_template_string(html, result=result)

if __name__ == "__main__":
    app.run(debug=True)