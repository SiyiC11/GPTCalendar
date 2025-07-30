from flask import Flask, redirect, session, url_for, request, jsonify
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json

app = Flask(__name__)
CORS(app)

# 設定 Flask 密鑰
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-super-secret-key-here-change-this")

# Google Calendar API 權限範圍
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# 重定向 URI
REDIRECT_URI = "https://gptcalendar.onrender.com/oauth2callback"

# Google OAuth 客戶端配置
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "project_id": "chatgpt-reminder-466905",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [REDIRECT_URI],
        "javascript_origins": ["https://gptcalendar.onrender.com"]
    }
}


def get_service():
    """獲取已認證的 Google Calendar 服務"""
    if "credentials" not in session:
        return None
    
    creds_data = session["credentials"]
    creds = Credentials(**creds_data)
    
    # 如果憑證過期且有 refresh token，則重新整理
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
    """首頁"""
    return "✅ GPTCalendar OAuth API is running. Use /login to authenticate."


@app.route("/debug")
def debug():
    """調試端點 - 檢查環境變數和配置"""
    return jsonify({
        "client_id": GOOGLE_CLIENT_CONFIG["web"]["client_id"],
        "client_secret_exists": bool(GOOGLE_CLIENT_CONFIG["web"]["client_secret"]),
        "redirect_uri": REDIRECT_URI,
        "flask_secret_exists": bool(app.secret_key),
        "session_exists": "credentials" in session,
        "project_id": GOOGLE_CLIENT_CONFIG["web"]["project_id"]
    })


@app.route("/login")
def login():
    """開始 OAuth 登入流程"""
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
    """處理 OAuth 回調"""
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
        
        # 獲取授權碼並交換為憑證
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # 儲存憑證到 session
        session["credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        
        return redirect("/success")
        
    except Exception as e:
        return jsonify({"error": f"認證回調失敗: {str(e)}"}), 400


@app.route("/success")
def success():
    """登入成功頁面"""
    if "credentials" not in session:
        return redirect("/login")
    
    return jsonify({
        "status": "success",
        "message": "✅ Login successful. You may now create/query/update/delete events.",
        "user_authenticated": True
    })


@app.route("/logout")
def logout():
    """登出"""
    session.clear()
    return jsonify({"status": "logged_out", "message": "Successfully logged out."})


@app.route("/create_event", methods=["POST"])
def create_event():
    """建立新的日曆事件"""
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # 驗證必要欄位
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
    """更新現有的日曆事件"""
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
        
        # 取得現有事件
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        
        # 更新指定的欄位
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
    """刪除日曆事件"""
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
        
        return jsonify({
            "status": "deleted",
            "event_id": event_id,
            "message": "Event successfully deleted"
        })
        
    except Exception as e:
        return jsonify({"error": f"刪除事件失敗: {str(e)}"}), 500


@app.route("/query_events", methods=["POST"])
def query_events():
    """查詢指定日期範圍內的日曆事件"""
    service = get_service()
    if not service:
        return jsonify({"error": "Not logged in. Please authenticate first."}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        start_date = data.get("start")
        end_date = data.get("end")
        timezone = data.get("timezone", "+10:00")  # 預設為澳洲時間
        
        if not start_date or not end_date:
            return jsonify({"error": "Missing start or end date"}), 400
        
        # 格式化時間
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
        
        # 格式化輸出
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


@app.route("/health")
def health():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "service": "GPTCalendar API",
        "authenticated": "credentials" in session
    })


# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # 本地開發時使用
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
