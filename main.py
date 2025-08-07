from flask import Flask, request, jsonify, send_from_directory, session, redirect, has_request_context
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json
import re

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

def validate_refresh_token_format(token):
    """驗證 refresh token 的格式"""
    if not token:
        return False, "Token 為空"
    
    # 移除前後空白
    token = token.strip()
    
    # 檢查長度（Google refresh token 通常在 100-200 字符之間）
    if len(token) < 50:
        return False, f"Token 太短 ({len(token)} 字符)，可能被截斷"
    
    if len(token) > 500:
        return False, f"Token 太長 ({len(token)} 字符)，可能包含額外內容"
    
    # 檢查是否包含不應該有的字符
    if '\n' in token or '\r' in token:
        return False, "Token 包含換行符，請檢查複製是否完整"
    
    if ' ' in token:
        return False, "Token 包含空格，請檢查複製是否正確"
    
    # Google refresh token 通常以特定前綴開始
    if not token.startswith('1//'):
        return False, f"Token 格式異常，不是以 '1//' 開始：{token[:10]}..."
    
    # 檢查是否只包含合法字符（Base64 URL safe + 特殊字符）
    valid_chars = re.match(r'^[A-Za-z0-9\-_/]+$', token)
    if not valid_chars:
        return False, "Token 包含非法字符"
    
    return True, "Token 格式看起來正確"

def load_credentials_from_env():
    """从环境变量加载持久化的凭证"""
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    
    if not refresh_token or not client_id or not client_secret:
        print(f"❌ 缺少必要的环境变量:")
        print(f"   GOOGLE_REFRESH_TOKEN: {'✅' if refresh_token else '❌'} ({len(refresh_token)} 字符)")
        print(f"   GOOGLE_CLIENT_ID: {'✅' if client_id else '❌'} ({len(client_id)} 字符)")
        print(f"   GOOGLE_CLIENT_SECRET: {'✅' if client_secret else '❌'} ({len(client_secret)} 字符)")
        return None
    
    # 🔍 詳細檢查 refresh token 格式
    print(f"🔍 詳細分析 refresh token:")
    print(f"   長度: {len(refresh_token)} 字符")
    print(f"   前15字符: {refresh_token[:15]}...")
    print(f"   後15字符: ...{refresh_token[-15:]}")
    
    is_valid, message = validate_refresh_token_format(refresh_token)
    if not is_valid:
        print(f"❌ Refresh token 格式問題: {message}")
        return None
    else:
        print(f"✅ Refresh token 格式檢查: {message}")
    
    try:
        creds = Credentials(
            token=None,  # 会通过 refresh 获得
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
        
        # 立即刷新获取有效的 access_token
        print("🔄 嘗試刷新 access token...")
        creds.refresh(Request())
        print("✅ 成功从环境变量恢复凭证")
        return creds
        
    except Exception as e:
        error_str = str(e)
        print(f"❌ 从环境变量恢复凭证失败: {error_str}")
        
        # 分析具體錯誤類型
        if "invalid_grant" in error_str.lower():
            print("💡 可能原因：")
            print("   1. refresh_token 已被 Google 撤銷")
            print("   2. client_id/client_secret 與產生 token 時不匹配")
            print("   3. 系統時間不準確")
            print("   4. token 已超過 6 個月未使用")
        elif "invalid_client" in error_str.lower():
            print("💡 可能原因：client_id 或 client_secret 錯誤")
        elif "network" in error_str.lower() or "connection" in error_str.lower():
            print("💡 可能原因：網路連接問題")
        
        print("🔧 建議解決方法：重新訪問 /login 進行授權")
        return None

def get_service():
    """獲取 Google Calendar 服務，優先從環境變數恢復憑證"""
    # 1. 優先嘗試從環境變數恢復（持久化）
    creds = load_credentials_from_env()
    
    # 2. 如果環境變數沒有，且在請求上下文中，嘗試從 session 獲取
    if not creds and has_request_context():
        try:
            if "credentials" in session:
                print("🔄 嘗試從 session 恢復憑證...")
                creds_data = session["credentials"]
                creds = Credentials(**creds_data)
                
                # 檢查是否過期並刷新
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        print("✅ Session 憑證刷新成功")
                    except Exception as e:
                        print(f"❌ Session 憑證刷新失敗: {e}")
                        return None
                else:
                    print("✅ 從 session 恢復憑證成功")
        except Exception as e:
            print(f"❌ 從 session 恢復憑證時發生錯誤: {e}")
    
    # 3. 都沒有的話返回 None
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
    print("🔑 請複製以下內容到 Render 環境變數設定中：")
    print("="*60)
    print(f"變數名: GOOGLE_REFRESH_TOKEN")
    print(f"變數值: {creds.refresh_token}")
    print("="*60)
    print("設定完成後，以後伺服器重啟都不需要重新登入了！")
    print("="*60 + "\n")
    
    # 驗證新產生的 token 格式
    is_valid, message = validate_refresh_token_format(creds.refresh_token)
    validation_msg = f"✅ {message}" if is_valid else f"⚠️ {message}"
    
    return f"""
    <h2>✅ 登入成功！</h2>
    <h3>🔑 請複製以下 refresh_token 到 Render 環境變數：</h3>
    <div style="background:#f0f0f0; padding:15px; margin:10px 0; border-radius:5px;">
        <strong>變數名:</strong> GOOGLE_REFRESH_TOKEN<br>
        <strong>變數值:</strong> <span style="color:red; font-family:monospace; word-break:break-all;">{creds.refresh_token}</span>
    </div>
    <div style="background:#e6f3ff; padding:10px; margin:10px 0; border-radius:5px;">
        <strong>🔍 Token 格式檢查:</strong> {validation_msg}
    </div>
    <h3>📋 設定步驟：</h3>
    <ol>
        <li>去 Render Dashboard → Environment</li>
        <li>點擊 "Add Environment Variable"</li>
        <li>Key: GOOGLE_REFRESH_TOKEN</li>
        <li>Value: 複製上面紅色的字串（整個字串，不要包含空格或換行）</li>
        <li>儲存後重新部署</li>
    </ol>
    <p><a href="/">返回首頁</a></p>
    """

# === CRUD endpoints ===

@app.route("/create_event", methods=["POST"])
def create_event():
    service = get_service()
    if not service:
        return jsonify({
            "error": "Not logged in", 
            "message": "請訪問 /login 進行授權，或檢查 GOOGLE_REFRESH_TOKEN 環境變數"
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
            "message": "請訪問 /login 進行授權，或檢查 GOOGLE_REFRESH_TOKEN 環境變數"
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
            "message": "請訪問 /login 進行授權，或檢查 GOOGLE_REFRESH_TOKEN 環境變數"
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
            "message": "請訪問 /login 進行授權，或檢查 GOOGLE_REFRESH_TOKEN 環境變數"
        }), 401
    data = request.json
    start = data.get("start")
    end = data.get("end")
    if not start or not end:
        return jsonify({"error": "Missing start or end"}), 400
    try:
        # 🔧 修復時間格式問題：移除硬編碼的時區偏移
        events = service.events().list(
            calendarId="primary",
            timeMin=start + "T00:00:00Z",  # 使用 UTC，讓 API 自己處理時區
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
    """檢查當前登入狀態"""
    has_env_token = bool(os.environ.get("GOOGLE_REFRESH_TOKEN"))
    has_session = has_request_context() and "credentials" in session
    service = get_service()
    
    # 檢查 refresh token 格式
    token_format_status = "未設定"
    if has_env_token:
        token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
        is_valid, message = validate_refresh_token_format(token)
        token_format_status = f"✅ {message}" if is_valid else f"❌ {message}"
    
    return jsonify({
        "env_token_exists": has_env_token,
        "token_format_check": token_format_status,
        "session_exists": has_session,
        "service_ready": bool(service),
        "message": "Ready to use!" if service else "需要登入授權"
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
    
    # 🔧 修復：在應用程式啟動時，不直接呼叫 get_service()
    # 改為在有請求上下文時才檢查服務狀態
    service_status = "未知"
    token_format_status = "未設定"
    
    if has_refresh_token:
        token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
        is_valid, message = validate_refresh_token_format(token)
        token_format_status = f"✅ {message}" if is_valid else f"❌ {message}"
        
        # 只有在請求上下文中才嘗試檢查服務
        try:
            service = get_service()
            service_status = "🟢 Ready!" if service else "🔴 需要登入"
        except Exception as e:
            service_status = f"🟡 檢查失敗: {str(e)[:50]}..."
    else:
        service_status = "🔴 需要設定環境變數"
    
    env_msg = "✅ 已配置" if has_refresh_token else "❌ 未配置"
    
    return f"""
    <h2>✅ GPTCalendar Backend</h2>
    <p><strong>服務狀態:</strong> {service_status}</p>
    <p><strong>環境變數:</strong> {env_msg}</p>
    <p><strong>Token 格式:</strong> {token_format_status}</p>
    <p><strong>登入連結:</strong> <a href="/login">/login</a></p>
    <p><strong>狀態檢查:</strong> <a href="/status">/status</a></p>
    <hr>
    <h3>🔧 除錯資訊</h3>
    <p>如果遇到問題，請檢查：</p>
    <ul>
        <li>環境變數是否正確設定</li>
        <li>Refresh token 是否完整（無空格、換行）</li>
        <li>Client ID/Secret 是否與產生 token 時一致</li>
    </ul>
    """

if __name__ == "__main__":
    # 🔧 修復：啟動時的環境變數檢查，避免在請求上下文外使用 session
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    
    print("🔍 環境變數檢查:")
    print(f"   GOOGLE_CLIENT_ID: {'✅' if client_id else '❌'} ({len(client_id)} 字符)")
    print(f"   GOOGLE_CLIENT_SECRET: {'✅' if client_secret else '❌'} ({len(client_secret)} 字符)")
    print(f"   GOOGLE_REFRESH_TOKEN: {'✅' if refresh_token else '❌'} ({len(refresh_token)} 字符)")
    
    if refresh_token:
        print("🔑 檢測到 GOOGLE_REFRESH_TOKEN 環境變數")
        
        # 檢查 token 格式但不嘗試使用 session
        is_valid, message = validate_refresh_token_format(refresh_token)
        if is_valid:
            print(f"✅ Token 格式檢查: {message}")
            print("🚀 應用程式啟動中... 將在首次 API 呼叫時驗證憑證")
        else:
            print(f"❌ Token 格式問題: {message}")
            print("💡 建議：重新訪問 /login 進行授權")
    else:
        print("⚠️  未檢測到 GOOGLE_REFRESH_TOKEN 環境變數")
        print("   首次使用請訪問 /login 進行授權")
    
    print("\n🚀 伺服器啟動中...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
