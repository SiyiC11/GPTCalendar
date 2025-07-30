
from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json

# === Flask app setup ===
app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key")

# === OAuth2 config ===
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = "https://gptcalendar.onrender.com/oauth2callback"

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "project_id": "gptcalendar",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uris": [REDIRECT_URI],
        "javascript_origins": ["https://gptcalendar.onrender.com"]
    }
}

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

def get_service():
    if "credentials" not in session:
        return None
    creds_data = session["credentials"]
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print("Failed to refresh credentials:", e)
            return None
    return build("calendar", "v3", credentials=creds)

# === Login Flow ===
@app.route("/login")
def login():
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    return jsonify({"status": "login successful"})

# === CRUD endpoints ===

@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    event = request.json
    try:
        result = service.events().insert(calendarId="primary", body=event).execute()
        return jsonify({"status": "created", "event_id": result.get("id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_event", methods=["POST"])
def update_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    event_id = data.get("eventId")
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        for k in ["summary", "description", "location", "start", "end", "recurrence", "reminders"]:
            if k in data:
                event[k] = data[k]
        updated = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return jsonify({"status": "updated", "event_id": updated.get("id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/delete_event", methods=["POST"])
def delete_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    event_id = data.get("eventId")
    if not event_id:
        return jsonify({"error": "Missing eventId"}), 400
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/query_events", methods=["POST"])
def query_events():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    start = data.get("start")
    end = data.get("end")
    if not start or not end:
        return jsonify({"error": "Missing start or end"}), 400
    try:
        events = service.events().list(
            calendarId="primary",
            timeMin=start + "T00:00:00+10:00",
            timeMax=end + "T23:59:59+10:00",
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        results = [{
            "summary": e.get("summary"),
            "start": e.get("start"),
            "end": e.get("end"),
            "eventId": e.get("id")
        } for e in events.get("items", [])]
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"Google Calendar API error: {str(e)}"}), 500

# === Plugin files & metadata ===

@app.route("/openapi.yaml")
def serve_openapi():
    return send_from_directory(".", "openapi.yaml", mimetype="text/yaml")

@app.route("/.well-known/ai-plugin.json")
def serve_ai_plugin():
    return send_from_directory(".well-known", "ai-plugin.json", mimetype="application/json")

@app.route("/privacy")
def privacy():
    return "<h2>Privacy</h2><p>This tool is for personal use only. No data is stored or shared.</p>"

@app.route("/")
def home():
    return "✅ GPTCalendar backend is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
