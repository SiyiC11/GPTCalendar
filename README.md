# ReminderGPT Plugin (安全版本)

這是安全版本的 ReminderGPT，不會在 GitHub 中暴露 client_secret.json，
改為透過環境變數 `GOOGLE_CREDS_B64` 傳遞憑證。

## Render 設定方式

1. 前往你建立的 Web Service
2. 點選左側「Environment」
3. 加入一筆環境變數：
   - KEY：`GOOGLE_CREDS_B64`
   - VALUE：請使用 base64 編碼後的 `client_secret.json`

4. 建立成功後，部署會自動讀取此憑證並運作。

## Base64 編碼方式 (在 macOS / Linux)
```bash
cat client_secret.json | base64
```

或在 Python 中：
```python
import base64, json
b64 = base64.b64encode(open("client_secret.json","rb").read()).decode()
print(b64)
```