from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import json
import base64

from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# 讀取並解碼 GOOGLE_CREDS_B64 環境變數
creds_b64 = os.environ.get("GOOGLE_CREDS_B64")
if creds_b64 is None:
    raise ValueError("Missing GOOGLE_CREDS_B64 environment variable")

creds_json = json.loads(base64.b64decode(creds_b64))
credentials = service_account.Credentials.from_service_account_info(creds_json)
calendar_id = 'primary'

# === 📆 建立行事曆提醒 API ===
@app.route("/create_reminder", methods=["POST"])
def create_reminder():
    data = request.json
    event = {
        'summary': data['summary'],
        'description': data.get('description', ''),
        'start': {
            'dateTime': data['start'],
            'timeZone': 'Australia/Sydney',
        },
        'end': {
            'dateTime': data['end'],
            'timeZone': 'Australia/Sydney',
        },
    }
    service = build("calendar", "v3", credentials=credentials)
    created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return jsonify({'event_id': created_event.get('id'), 'status': 'success'})

# === 🧩 提供 Plugin 所需靜態檔 ===
@app.route("/.well-known/ai-plugin.json")
def serve_ai_plugin():
    return send_from_directory(".well-known", "ai-plugin.json", mimetype="application/json")

@app.route("/openapi.yaml")
def serve_openapi():
    return send_from_directory(".", "openapi.yaml", mimetype="text/yaml")

# === 🏁 主程式入口（可省略 Render 會自動呼叫）===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
