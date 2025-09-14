import re
import fitz  # PyMuPDF
from flask import Flask, request, render_template_string
from rapidfuzz import fuzz

# برای OCR
import pytesseract
from pdf2image import convert_from_bytes

app = Flask(__name__)

# ----------------------------
# کلیدواژه‌ها
# ----------------------------
keywords_map = {
    "Beneficiary": ["beneficiary", "beneficiary name", "payee", "receiver", "seller"],
    "Bank": ["bank", "bank name", "issuing bank", "beneficiary bank", "banking information", "bank address"],
    "Account No": ["account no", "a/c no", "iban", "account number", "acc no"],
    "SWIFT Code": ["swift", "swift code", "bic", "bic code"],
    "Currency": ["currency", "curr", "payment currency", "type of currency"],
    "Amount": ["amount", "total amount", "invoice amount", "total", "sum"]
}

# ----------------------------
# توابع کمکی
# ----------------------------
def normalize(text):
    return re.sub(r'\s+', ' ', text.strip().lower())


def match_keyword(text, keywords, threshold=75):
    for kw in keywords:
        if fuzz.partial_ratio(kw, text) >= threshold:
            return kw
    return None


def extract_value(line, keyword):
    """مقدار بعد از کلیدواژه یا خط بعدی"""
    pattern = re.compile(rf"{re.escape(keyword)}[:\-]?\s*(.*)", re.IGNORECASE)
    match = pattern.search(line)
    if match and match.group(1).strip():
        return match.group(1).strip()
    return ""


def extract_info(text):
    # پیش‌فرض: همه فیلدها = "یافت نشد"
    results = {k: "یافت نشد" for k in keywords_map.keys()}
    lines = text.split("\n")

    for i, line in enumerate(lines):
        norm_line = normalize(line)
        for field, kw_list in keywords_map.items():
            if results[field] != "یافت نشد":  # اگر پر شده، بیخیال
                continue
            if kw := match_keyword(norm_line, kw_list):
                value = extract_value(line, kw)
                if not value and i + 1 < len(lines):
                    value = lines[i + 1].strip()
                if value:
                    results[field] = value
    return results


def read_pdf(file_bytes):
    """اول متن مستقیم، اگه ناقص بود OCR"""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"

    # اگر متن خالی یا خیلی کوتاه بود → OCR
    if len(text.strip()) < 50:
        images = convert_from_bytes(file_bytes)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang="eng") + "\n"
        return ocr_text
    return text


# ----------------------------
# روت
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    if request.method == "POST":
        file = request.files["file"]
        if file:
            file_bytes = file.read()
            text = read_pdf(file_bytes)
            data = extract_info(text)

    return render_template_string("""
        <h2>آپلود فایل PDF</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="بررسی">
        </form>

        {% if data %}
            <h3>ویژگی‌های اصلی:</h3>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><th>فیلد</th><th>مقدار</th></tr>
                {% for key, value in data.items() %}
                    <tr>
                        <td><b>{{ key }}</b></td>
                        <td>{{ value }}</td>
                    </tr>
                {% endfor %}
            </table>
        {% endif %}
    """, data=data)


if __name__ == "__main__":
    app.run(debug=True)