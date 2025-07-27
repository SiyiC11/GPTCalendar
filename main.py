from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
import base64

app = Flask(__name__)
CORS(app)

# === 認證設定 ===
creds_b64 = os.environ.get("GOOGLE_CREDS_B64")
if not creds_b64:
    raise ValueError("Missing GOOGLE_CREDS_B64 environment variable")
creds_json = json.loads(base64.b64decode(creds_b64))
credentials = service_account.Credentials.from_service_account_info(creds_json)
calendar_id = "cwp319203@gmail.com"

def get_calendar_service():
    return build("calendar", "v3", credentials=credentials)

# === 建立事件 ===
@app.route("/create_event", methods=["POST"])
def create_event():
    event = request.json
    service = get_calendar_service()
    try:
        result = service.events().insert(calendarId=calendar_id, body=event).execute()
        return jsonify({"status": "created", "event_id": result.get("id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 更新事件 ===
@app.route("/update_event", methods=["POST"])
def update_event():
    data = request.json
    event_id = data.get("eventId")
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    service = get_calendar_service()
    try:
        # Get current event and update fields
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        for k in ["summary", "description", "location", "start", "end", "recurrence"]:
            if k in data:
                event[k] = data[k]
        updated = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return jsonify({"status": "updated", "event_id": updated.get("id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 刪除事件 ===
@app.route("/delete_event", methods=["POST"])
def delete_event():
    data = request.json
    event_id = data.get("eventId")
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    service = get_calendar_service()
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 查詢事件 ===
@app.route("/query_events", methods=["POST"])
def query_events():
    data = request.json
    start = data.get("start")
    end = data.get("end")
    if not start or not end:
        return jsonify({"error": "Missing start or end"}), 400
    service = get_calendar_service()
    try:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start + "T00:00:00",
            timeMax=end + "T23:59:59",
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        return jsonify(events.get("items", []))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 靜態文件路由 ===
@app.route("/openapi.yaml")
def serve_openapi():
    return send_from_directory(".", "openapi.yaml", mimetype="text/yaml")

@app.route("/.well-known/ai-plugin.json")
def serve_ai_plugin():
    return send_from_directory(".well-known", "ai-plugin.json", mimetype="application/json")

# === 健康檢查 ===
@app.route("/")
def home():
    return "GPTCalendar backend is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
