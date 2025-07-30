
from flask import Flask, redirect, session, url_for, request, jsonify
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "secret")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = "https://gptcalendar.onrender.com/oauth2callback"

def get_service():
    if "credentials" not in session:
        return None
    creds_data = session["credentials"]
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session["credentials"]["token"] = creds.token
    return build("calendar", "v3", credentials=creds)

@app.route("/")
def index():
    return "✅ GPTCalendar OAuth API is running. Use /login to authenticate."

@app.route("/login")
def login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    session["state"] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }
    return redirect("/success")

@app.route("/success")
def success():
    return "✅ Login successful. You may now create/query/update/delete events."

@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    try:
        result = service.events().insert(calendarId="primary", body=data).execute()
        return jsonify({"status": "created", "event_id": result.get("id"), "summary": result.get("summary")})
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
        return jsonify({"status": "updated", "event_id": updated.get("id"), "summary": updated.get("summary")})
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
        return jsonify({"status": "deleted", "event_id": event_id})
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
        output = []
        for e in events.get("items", []):
            output.append({
                "eventId": e.get("id"),
                "summary": e.get("summary"),
                "start": e.get("start"),
                "end": e.get("end")
            })
        return jsonify({"events": output})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
