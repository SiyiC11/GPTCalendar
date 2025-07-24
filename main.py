from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import json
import base64
from collections import Counter

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
    time_zone = data.get('user_timezone', 'Australia/Sydney')

    event = {
        'summary': data['summary'],
        'description': data.get('description', ''),
        'start': {
            'dateTime': data['start'],
            'timeZone': time_zone,
        },
        'end': {
            'dateTime': data['end'],
            'timeZone': time_zone,
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
        event['start']['timeZone'] = data.get('user_timezone', event['start'].get('timeZone', 'Australia/Sydney'))
        event['end']['timeZone'] = data.get('user_timezone', event['end'].get('timeZone', 'Australia/Sydney'))

        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return jsonify({'status': 'updated', 'event_id': updated_event.get('id')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === 🔍 查詢事件（指定區間） ===
@app.route("/query_events", methods=["GET"])
def query_events():
    start_str = request.args.get('start')  # YYYY-MM-DD
    end_str = request.args.get('end')      # YYYY-MM-DD
    if not start_str or not end_str:
        return jsonify({'error': 'Missing start or end date'}), 400

    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)
        service = get_calendar_service()
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat() + 'T00:00:00+10:00',
            timeMax=end_dt.isoformat() + 'T00:00:00+10:00',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === 📊 分析事件 ===
@app.route("/analyze_events", methods=["POST"])
def analyze_events():
    data = request.json
    analysis_type = data.get("analysis_type")
    start = data.get("date_range", {}).get("start")
    end = data.get("date_range", {}).get("end")
    keywords = data.get("filter_keywords", [])

    if not start or not end or not analysis_type:
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        service = get_calendar_service()
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat() + 'T00:00:00+10:00',
            timeMax=end_dt.isoformat() + 'T00:00:00+10:00',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if keywords:
            events = [e for e in events if any(k.lower() in e.get('summary', '').lower() for k in keywords)]

        if analysis_type == "event_count":
            return jsonify({"count": len(events)})
        elif analysis_type == "event_list":
            return jsonify({"events": events})
        elif analysis_type == "busiest_day":
            counter = Counter(e['start']['dateTime'][:10] for e in events)
            busiest = counter.most_common(1)
            return jsonify({"busiest_day": busiest[0] if busiest else None})
        elif analysis_type == "emptiest_day":
            counter = Counter(e['start']['dateTime'][:10] for e in events)
            all_days = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_dt - start_dt).days)]
            emptiest = min(all_days, key=lambda d: counter.get(d, 0))
            return jsonify({"emptiest_day": emptiest})
        elif analysis_type == "most_common_event":
            names = [e.get("summary", "") for e in events]
            most = Counter(names).most_common(1)
            return jsonify({"most_common_event": most[0] if most else None})
        elif analysis_type == "summary":
            total = len(events)
            kinds = Counter(e.get("summary", "") for e in events)
            return jsonify({"total": total, "breakdown": kinds})

        return jsonify({"error": "Invalid analysis_type"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
