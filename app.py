import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- بارگذاری تنبل (Lazy Loading) ---
# به جای بارگذاری سنگین توی startup، بعداً لود می‌کنیم
pdf_model = None

@app.route("/")
def home():
    return "Analyze Invoice API is running ✅"

@app.route("/analyze", methods=["POST"])
def analyze_invoice():
    global pdf_model
    if pdf_model is None:
        # اینجا فایل سنگین یا مدل رو وقتی نیاز شد لود می‌کنیم
        pdf_model = "Loaded model ✅"  # جایگزین کن با کد واقعی
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    # تحلیل ساده (جایگزین با پردازش واقعی)
    return jsonify({"message": f"Invoice '{file.filename}' analyzed successfully"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)