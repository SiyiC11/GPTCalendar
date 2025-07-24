from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'client_secret.json'
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

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