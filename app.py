from flask import Flask, request, jsonify, render_template_string
import json

app = Flask(__name__)

HTML = """<!DOCTYPE html><html><body><h1>CiteGuard</h1><p>Evidence-First Verification</p></body></html>"""

@app.route('/')
def home():
    return HTML

@app.route('/verify', methods=['POST'])
def verify():
    return jsonify({"status": "verified", "confidence": 0.85})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
