import re
import fitz  # PyMuPDF
from flask import Flask, request, render_template_string
from rapidfuzz import fuzz

app = Flask(__name__)

# ----------------------------
# کلیدواژه‌ها
# ----------------------------
beneficiary_keywords = [
    "beneficiary", "beneficiary name", "beneficiary's name", 
    "receiver", "payee", "seller"
]

bank_keywords = [
    "bank", "bank name", "issuing bank", "beneficiary bank", 
    "banking information", "bank address"
]

account_keywords = [
    "account no", "a/c no", "iban", "account number", "acc no"
]

swift_keywords = [
    "swift", "swift code", "bic", "bic code"
]

currency_keywords = [
    "currency", "curr", "payment currency", "type of currency"
]

amount_keywords = [
    "amount", "total amount", "invoice amount", "total", "sum"
]

# ----------------------------
# توابع کمکی
# ----------------------------
def normalize(text):
    return re.sub(r'\s+', ' ', text.strip().lower())


def match_keyword(text, keywords, threshold=75):
    """بررسی شباهت متن با کلیدواژه‌ها"""
    for kw in keywords:
        if fuzz.partial_ratio(kw, text) >= threshold:
            return kw
    return None


def extract_value(line, keyword):
    """گرفتن مقدار بعد از کلیدواژه یا علامت :"""
    # اگه با : یا - جدا شده باشه
    pattern = re.compile(rf"{re.escape(keyword)}[:\-]?\s*(.*)", re.IGNORECASE)
    match = pattern.search(line)
    if match:
        return match.group(1).strip()
    # اگر فقط کلیدواژه تو خط باشه و مقدار بعدش بیاد
    words = line.split()
    if keyword.lower() in line.lower():
        idx = line.lower().index(keyword.lower()) + len(keyword)
        return line[idx:].strip(" :.-")
    return line.strip()


def extract_info(text):
    """استخراج اطلاعات مهم از متن PDF"""
    results = {
        "Beneficiary": "",
        "Bank": "",
        "Account No": "",
        "SWIFT Code": "",
        "Currency": "",
        "Amount": ""
    }

    lines = text.split("\n")
    for line in lines:
        norm_line = normalize(line)

        if kw := match_keyword(norm_line, beneficiary_keywords):
            results["Beneficiary"] = extract_value(line, kw)
        elif kw := match_keyword(norm_line, bank_keywords):
            results["Bank"] = extract_value(line, kw)
        elif kw := match_keyword(norm_line, account_keywords):
            results["Account No"] = extract_value(line, kw)
        elif kw := match_keyword(norm_line, swift_keywords):
            results["SWIFT Code"] = extract_value(line, kw)
        elif kw := match_keyword(norm_line, currency_keywords):
            results["Currency"] = extract_value(line, kw)
        elif kw := match_keyword(norm_line, amount_keywords):
            results["Amount"] = extract_value(line, kw)

    return results

# ----------------------------
# روت‌ها
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    if request.method == "POST":
        file = request.files["file"]
        if file:
            doc = fitz.open(stream=file.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n"

            data = extract_info(text)

    return render_template_string("""
        <h2>آپلود فایل PDF</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="بررسی">
        </form>

        {% if data %}
            <h3>نتایج:</h3>
            <ul>
                {% for key, value in data.items() %}
                    <li><b>{{ key }}</b>: {{ value }}</li>
                {% endfor %}
            </ul>
        {% endif %}
    """, data=data)


if __name__ == "__main__":
    app.run(debug=True)