from flask import Flask, request, render_template, jsonify
from pdf2image import convert_from_bytes
import pytesseract
import re

app = Flask(__name__)

def cleanup_text(s):
    return re.sub(r'\s+', ' ', s).strip()

def extract_from_text(text):
    out = {'beneficiary': None, 'total': None, 'currency': None, 'bank': None, 'account': None}
    m = re.search(r'(گیرنده|Beneficiary)\s*[:\-]?\s*(.+)', text)
    if m:
        out['beneficiary'] = cleanup_text(m.group(2))
    m = re.search(r'(جمع\s+کل|Total|Amount)\s*[:\-]?\s*([0-9\.,\s]+)\s*([A-Za-z]{3}|ریال|تومان|IRR|USD|EUR)?', text)
    if m:
        out['total'] = re.sub(r'[^0-9.,]', '', m.group(2))
        out['currency'] = m.group(3) or ''
    m = re.search(r'(IR[0-9]{24})', text)
    if m:
        out['account'] = m.group(1)
    m = re.search(r'بانک\s+([^\n]+)', text)
    if m:
        out['bank'] = cleanup_text(m.group(1))
    return out

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error':'no file'}),400
    f = request.files['file']
    data = f.read()
    pages = convert_from_bytes(data, dpi=200)
    results=[]
    for i,page in enumerate(pages,1):
        text=pytesseract.image_to_string(page, lang='fas+eng')
        extracted=extract_from_text(text)
        results.append({'page':i,'extracted':extracted,'text_snippet':text[:500]})
    return jsonify({'pages':results})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000)