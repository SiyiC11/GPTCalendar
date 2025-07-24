from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import json
import base64
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# 讀取 GOOGLE_CREDS_B64 環境變數並解碼為 JSON
creds_b64 = os.environ.get("GOOGLE_CREDS_B64")
if creds_b64 is None:
    raise ValueError("Missing GOOGLE_CREDS_B64 environment variable")

creds_json = json.loads(base64.b64decode(creds_b64))
credentials = service_account.Credentials.from_service_account_info(creds_json)

calendar_id = 'primary'

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
    service = build('calendar', 'v3', credentials=credentials)
    event_result = service.events().insert(calendarId=calendar_id, body=event).execute()
    return jsonify({"event_link": event_result.get("htmlLink")})

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
