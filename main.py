from flask import Flask, redirect, session, url_for, request, jsonify, render_template_string
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-super-secret-key-here-change-this")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = "https://gptcalendar.onrender.com/oauth2callback"

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "project_id": "chatgpt-reminder-466905",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uris": [REDIRECT_URI],
        "javascript_origins": ["https://gptcalendar.onrender.com"]
    }
}

def get_service():
    if "credentials" not in session:
        return None
    creds_data = session["credentials"]
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            session["credentials"]["token"] = creds.token
        except Exception as e:
            print(f"重新整理憑證失敗: {e}")
            return None
    return build("calendar", "v3", credentials=creds)


@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    event = service.events().insert(calendarId="primary", body=data).execute()
    return jsonify({"status": "created", "eventId": event.get("id")}), 200

@app.route("/update_event", methods=["POST"])
def update_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    event_id = data.pop("eventId", None)
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    event = service.events().update(calendarId="primary", eventId=event_id, body=data).execute()
    return jsonify({"status": "updated", "eventId": event.get("id")}), 200

@app.route("/delete_event", methods=["POST"])
def delete_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    event_id = data.get("eventId")
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return jsonify({"status": "deleted", "eventId": event_id}), 200

@app.route("/query_event", methods=["POST"])
def query_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    start = data.get("start") + "T00:00:00+10:00"
    end = data.get("end") + "T23:59:59+10:00"
    events_result = service.events().list(
        calendarId="primary",
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = [
        {
            "summary": e.get("summary"),
            "start": e.get("start"),
            "end": e.get("end"),
            "eventId": e.get("id")
        } for e in events_result.get("items", [])
    ]
    return jsonify(events), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
