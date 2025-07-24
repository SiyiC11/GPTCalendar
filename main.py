from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import json
import base64

from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# === 🔐 認證 ===
creds_b64 = os.environ.get("GOOGLE_CREDS_B64")
if creds_b64 is None:
    raise ValueError("Missing GOOGLE_CREDS_B64 environment variable")

creds_json = json.loads(base64.b64decode(creds_b64))
credentials = service_account.Credentials.from_service_account_info(creds_json)
calendar_id = 'cwp319203@gmail.com'

# === 📆 Google Calendar 服務 ===
def get_calendar_service():
    return build("calendar", "v3", credentials=credentials)

# === 🆕 建立事件 ===
@app.route("/create_event", methods=["POST"])
def create_event():
    data = request.json
    service = get_calendar_service()

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

    if 'recurrence' in data:
        event['recurrence'] = [data['recurrence']]

    created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return jsonify({'event_id': created_event.get('id'), 'status': 'created'})

# === 🗑️ 刪除事件 ===
@app.route("/delete_event", methods=["POST"])
def delete_event():
    data = request.json
    service = get_calendar_service()

    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'error': 'Missing event_id'}), 400

    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === ✏️ 修改事件 ===
@app.route("/update_event", methods=["POST"])
def update_event():
    data = request.json
    service = get_calendar_service()
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'error': 'Missing event_id'}), 400

    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        event['summary'] = data.get('summary', event.get('summary'))
        event['description'] = data.get('description', event.get('description'))
        event['start']['dateTime'] = data.get('start', event['start']['dateTime'])
        event['end']['dateTime'] = data.get('end', event['end']['dateTime'])

        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return jsonify({'status': 'updated', 'event_id': updated_event.get('id')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === 🔍 查詢事件（特定日期） ===
@app.route("/query_events", methods=["GET"])
def query_events():
    date_str = request.args.get('date')  # 格式 YYYY-MM-DD
    if not date_str:
        return jsonify({'error': 'Missing date parameter'}), 400

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        start_of_day = date_obj.isoformat() + 'T00:00:00+10:00'
        end_of_day = date_obj.isoformat() + 'T23:59:59+10:00'

        service = get_calendar_service()
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === 📄 Plugin 所需檔案 ===
@app.route("/.well-known/ai-plugin.json")
def serve_ai_plugin():
    return send_from_directory(".well-known", "ai-plugin.json", mimetype="application/json")

@app.route("/openapi.yaml")
def serve_openapi():
    return send_from_directory(".", "openapi.yaml", mimetype="text/yaml")

# === 🏁 主程式入口 ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
