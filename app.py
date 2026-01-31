from flask import Flask, request, jsonify, render_template_string
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)

# HTML Template for the frontend
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CiteGuard - Evidence-First Verification</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
        .container { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; margin-bottom: 30px; }
        textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; resize: vertical; }
        button { background: #3498db; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 4px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #2980b9; }
        .result { margin-top: 20px; padding: 20px; border-radius: 4px; display: none; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .confidence { font-weight: bold; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>CiteGuard</h1>
        <p class="subtitle">Evidence-First Claim Verification</p>
        
        <form id="verifyForm">
            <textarea id="claim" rows="4" placeholder="Enter claim to verify (5-1000 characters)..."></textarea>
            <br>
            <button type="submit">Verify Claim</button>
        </form>
        
        <div id="result" class="result"></div>
    </div>

    <script>
        document.getElementById('verifyForm').onsubmit = async (e) => {
            e.preventDefault();
            const claim = document.getElementById('claim').value;
            const resultDiv = document.getElementById('result');
            
            if (claim.length < 5 || claim.length > 1000) {
                resultDiv.className = 'result error';
                resultDiv.style.display = 'block';
                resultDiv.textContent = 'Claim must be between 5 and 1000 characters';
                return;
            }
            
            try {
                const response = await fetch('/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({claim: claim})
                });
                const data = await response.json();
                
                resultDiv.className = 'result success';
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `
                    <div>Status: ${data.status}</div>
                    <div class="confidence">Confidence: ${(data.confidence * 100).toFixed(1)}%</div>
                    ${data.sources ? '<div>Sources: ' + data.sources.join(', ') + '</div>' : ''}
                `;
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.style.display = 'block';
                resultDiv.textContent = 'Verification failed: ' + error.message;
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        
        # Manual validation (no Pydantic needed)
        if not data or 'claim' not in data:
            return jsonify({"error": "Missing 'claim' field"}), 400
            
        claim = data['claim']
        if not isinstance(claim, str):
            return jsonify({"error": "Claim must be a string"}), 400
            
        if len(claim) < 5 or len(claim) > 1000:
            return jsonify({"error": "Claim must be between 5 and 1000 characters"}), 400
        
        # Your verification logic here
        # Example mock implementation:
        confidence = min(0.95, max(0.1, len(claim) / 200))  # Mock confidence score
        
        return jsonify({
            "status": "verified",
            "confidence": round(confidence, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "claim_preview": claim[:50] + "..." if len(claim) > 50 else claim
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
