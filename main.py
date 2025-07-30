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

def load_credentials_from_env():
    """从环境变量加载持久化的凭证"""
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    if not refresh_token:
        return None
    
    try:
        creds = Credentials(
            token=None,  # 会通过 refresh 获得
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES
        )
        
        # 立即刷新获取有效的 access_token
        creds.refresh(Request())
        print("✅ 成功从环境变量恢复凭证")
        return creds
    except Exception as e:
        print(f"❌ 从环境变量恢复凭证失败: {e}")
        return None

def get_service():
    """获取 Google Calendar 服务，优先从环境变量恢复凭证"""
    # 1. 优先尝试从环境变量恢复（持久化）
    creds = load_credentials_from_env()
    
    # 2. 如果环境变量没有，尝试从 session 获取
    if not creds and "credentials" in session:
        creds_data = session["credentials"]
        creds = Credentials(**creds_data)
        
        # 检查是否过期并刷新
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print("Session 凭证刷新失败:", e)
                return None
    
    # 3. 都没有的话返回 None
    if not creds:
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
    
    # 保存到 session（临时）
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    
    # 🔥 重要：打印 refresh_token 供用户复制到环境变量
    print("\n" + "="*60)
    print("🔑 请复制以下内容到 Render 环境变量设置中：")
    print("="*60)
    print(f"变量名: GOOGLE_REFRESH_TOKEN")
    print(f"变量值: {creds.refresh_token}")
    print("="*60)
    print("设置完成后，以后服务器重启都不需要重新登录了！")
    print("="*60 + "\n")
    
    return jsonify({
        "status": "login successful", 
        "message": "请查看服务器日志，复制 GOOGLE_REFRESH_TOKEN 到环境变量中"
    })

# === CRUD endpoints ===

@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({
            "error": "Not logged in", 
            "message": "请访问 /login 进行授权，或检查 GOOGLE_REFRESH_TOKEN 环境变量"
        }), 401
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
        return jsonify({
            "error": "Not logged in", 
            "message": "请访问 /login 进行授权，或检查 GOOGLE_REFRESH_TOKEN 环境变量"
        }), 401
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
        return jsonify({
            "error": "Not logged in", 
            "message": "请访问 /login 进行授权，或检查 GOOGLE_REFRESH_TOKEN 环境变量"
        }), 401
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
        return jsonify({
            "error": "Not logged in", 
            "message": "请访问 /login 进行授权，或检查 GOOGLE_REFRESH_TOKEN 环境变量"
        }), 401
    data = request.json
    start = data.get("start")
    end = data.get("end")
    if not start or not end:
        return jsonify({"error": "Missing start or end"}), 400
    try:
        # 🔧 修复时间格式问题：移除硬编码的时区偏移
        events = service.events().list(
            calendarId="primary",
            timeMin=start + "T00:00:00Z",  # 使用 UTC，让 API 自己处理时区
            timeMax=end + "T23:59:59Z",
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

# === Status check endpoint ===
@app.route("/status")
def status():
    """检查当前登录状态"""
    has_env_token = bool(os.environ.get("GOOGLE_REFRESH_TOKEN"))
    has_session = "credentials" in session
    service = get_service()
    
    return jsonify({
        "env_token_exists": has_env_token,
        "session_exists": has_session,
        "service_ready": bool(service),
        "message": "Ready to use!" if service else "需要登录授权"
    })

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
    has_refresh_token = bool(os.environ.get("GOOGLE_REFRESH_TOKEN"))
    service = get_service()
    
    status_msg = "🟢 Ready!" if service else "🔴 需要登录"
    env_msg = "✅ 已配置" if has_refresh_token else "❌ 未配置"
    
    return f"""
    <h2>✅ GPTCalendar Backend</h2>
    <p><strong>服务状态:</strong> {status_msg}</p>
    <p><strong>环境变量:</strong> {env_msg}</p>
    <p><strong>登录链接:</strong> <a href="/login">/login</a></p>
    <p><strong>状态检查:</strong> <a href="/status">/status</a></p>
    """

if __name__ == "__main__":
    # 启动时检查环境变量配置
    if os.environ.get("GOOGLE_REFRESH_TOKEN"):
        print("🔑 检测到 GOOGLE_REFRESH_TOKEN 环境变量")
        service = get_service()
        if service:
            print("✅ 凭证有效，无需重新登录！")
        else:
            print("❌ 凭证无效，可能需要重新登录")
    else:
        print("⚠️  未检测到 GOOGLE_REFRESH_TOKEN 环境变量")
        print("   首次使用请访问 /login 进行授权")
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
