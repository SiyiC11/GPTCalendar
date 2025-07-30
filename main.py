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

@app.route("/")
def index():
    return "✅ GPTCalendar OAuth API is running. Use /login to authenticate."

@app.route("/debug")
def debug():
    client_id_raw = os.environ.get("GOOGLE_CLIENT_ID", "NOT_SET")
    client_secret_raw = os.environ.get("GOOGLE_CLIENT_SECRET", "NOT_SET")
    return jsonify({
        "client_id": GOOGLE_CLIENT_CONFIG["web"]["client_id"],
        "client_id_raw": repr(client_id_raw),
        "client_id_length": len(client_id_raw) if client_id_raw != "NOT_SET" else 0,
        "client_secret_exists": bool(GOOGLE_CLIENT_CONFIG["web"]["client_secret"]),
        "client_secret_raw": repr(client_secret_raw[:15] + "...") if client_secret_raw != "NOT_SET" else "NOT_SET",
        "client_secret_length": len(client_secret_raw) if client_secret_raw != "NOT_SET" else 0,
        "redirect_uri": REDIRECT_URI,
        "flask_secret_exists": bool(app.secret_key),
        "session_exists": "credentials" in session,
        "project_id": GOOGLE_CLIENT_CONFIG["web"]["project_id"],
        "javascript_origins": GOOGLE_CLIENT_CONFIG["web"]["javascript_origins"]
    })

@app.route("/login")
def login():
    try:
        flow = Flow.from_client_config(
            client_config=GOOGLE_CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true"
        )
        session["state"] = state
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": f"登入失敗: {str(e)}"}), 500

@app.route("/oauth2callback")
def oauth2callback():
    try:
        state = session.get("state")
        if not state:
            return "⚠️ Missing session state. Please try logging in again.", 400

        flow = Flow.from_client_config(
            client_config=GOOGLE_CLIENT_CONFIG,
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
        html = f"""
        <script>
        window.opener.postMessage({{
            token: "{credentials.token}"
        }}, "*");
        window.close();
        </script>
        <p>✅ 登入成功！您可以關閉此視窗。</p>
        """
        return render_template_string(html)
    except Exception as e:
        return jsonify({"error": f"認證回調失敗: {str(e)}"}), 400

@app.route("/success")
def success():
    if "credentials" not in session:
        return redirect("/login")
    return jsonify({
        "status": "success",
        "message": "✅ Login successful. You may now create/query/update/delete events.",
        "user_authenticated": True
    })

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"status": "logged_out", "message": "Successfully logged out."})

@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        required_fields = ["summary", "start", "end"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        result = service.events().insert(calendarId="primary", body=data).execute()
        return jsonify({
            "status": "created",
            "event_id": result.get("id"),
            "summary": result.get("summary"),
            "start": result.get("start"),
            "end": result.get("end"),
            "html_link": result.get("htmlLink")
        })
    except Exception as e:
        return jsonify({"error": f"建立事件失敗: {str(e)}"}), 500

@app.route("/update_event", methods=["POST"])
def update_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        event_id = data.get("eventId")
        if not event_id:
            return jsonify({"error": "Missing eventId"}), 400
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        updateable_fields = ["summary", "description", "location", "start", "end", "recurrence", "reminders"]
        for field in updateable_fields:
            if field in data:
                event[field] = data[field]
        updated = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return jsonify({
            "status": "updated",
            "event_id": updated.get("id"),
            "summary": updated.get("summary"),
            "start": updated.get("start"),
            "end": updated.get("end")
        })
    except Exception as e:
        return jsonify({"error": f"更新事件失敗: {str(e)}"}), 500

@app.route("/delete_event", methods=["POST"])
def delete_event():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        event_id = data.get("eventId")
        if not event_id:
            return jsonify({"error": "Missing eventId"}), 400
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return jsonify({"status": "deleted", "event_id": event_id, "message": "Event successfully deleted"})
    except Exception as e:
        return jsonify({"error": f"刪除事件失敗: {str(e)}"}), 500

@app.route("/query_events", methods=["POST"])
def query_events():
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        start_date = data.get("start")
        end_date = data.get("end")
        timezone = data.get("timezone", "+10:00")
        if not start_date or not end_date:
            return jsonify({"error": "Missing start or end date"}), 400
        time_min = f"{start_date}T00:00:00{timezone}"
        time_max = f"{end_date}T23:59:59{timezone}"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=100
        ).execute()
        events = events_result.get("items", [])
        formatted_events = []
        for event in events:
            formatted_events.append({
                "eventId": event.get("id"),
                "summary": event.get("summary", "無標題"),
                "description": event.get("description", ""),
                "start": event.get("start"),
                "end": event.get("end"),
                "location": event.get("location", ""),
                "status": event.get("status"),
                "html_link": event.get("htmlLink")
            })
        return jsonify({
            "events": formatted_events,
            "total_count": len(formatted_events),
            "query_range": {
                "start": start_date,
                "end": end_date,
                "timezone": timezone
            }
        })
    except Exception as e:
        return jsonify({"error": f"查詢事件失敗: {str(e)}"}), 500

@app.route("/privacy")
def privacy():
    return """
    <html><head><title>Privacy Policy - GPTCalendar</title></head>
    <body><h1>Privacy Policy</h1>
    <p>This application accesses your Google Calendar to manage events on your behalf.</p>
    <p>We do not store or share your personal information.</p>
    <p>All data is processed securely and only used for the intended calendar management purposes.</p>
    <p><a href="/">← Back to Home</a></p>
    </body></html>
    """

@app.route("/terms")
def terms():
    return """
    <html><head><title>Terms of Service - GPTCalendar</title></head>
    <body><h1>Terms of Service</h1>
    <p>By using this application, you agree to allow it to access your Google Calendar.</p>
    <p>This is a demo application for educational purposes.</p>
    <p>Use at your own risk.</p>
    <p><a href="/">← Back to Home</a></p>
    </body></html>
    """

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
from flask import send_from_directory

@app.route("/openapi.yaml")
def openapi_spec():
    return send_from_directory(".", "openapi.yaml", mimetype="text/yaml")

@app.route("/.well-known/ai-plugin.json")
def plugin_manifest():
    return send_from_directory(".well-known", "ai-plugin.json", mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)


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
