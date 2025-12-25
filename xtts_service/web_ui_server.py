#!/usr/bin/env python3
"""
XTTS Web UI Server
Referans ses yönetimi için web arayüzü
Port: 8696
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import requests

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_UI_DIR = os.path.join(BASE_DIR, "web_ui")
STATIC_DIR = os.path.join(WEB_UI_DIR, "static")
TEMPLATES_DIR = os.path.join(WEB_UI_DIR, "templates")
XTTS_API_URL = os.getenv("XTTS_API_URL", "http://localhost:8020")
PORT = int(os.getenv("WEB_UI_PORT", 8696))

# Ensure directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="XTTS Web UI")

# Mount static files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
if os.path.exists(TEMPLATES_DIR):
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
else:
    templates = None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Web UI ana sayfası"""
    if templates:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "xtts_api_url": XTTS_API_URL
        })
    else:
        return HTMLResponse("""
        <html>
            <head><title>XTTS Web UI</title></head>
            <body>
                <h1>❌ Web UI dosyaları bulunamadı</h1>
                <p>Lütfen <code>web_ui/templates/index.html</code> dosyasının var olduğundan emin olun.</p>
            </body>
        </html>
        """)

# Proxy endpoints - XTTS API'ye yönlendirme
@app.get("/api/voices")
async def proxy_voices():
    """Sesleri listele (proxy)"""
    try:
        response = requests.get(f"{XTTS_API_URL}/voices", timeout=5)
        return response.json()
    except Exception as e:
        return {"error": str(e), "voices": []}

@app.get("/api/voices/active")
async def proxy_active_voice():
    """Aktif sesi getir (proxy)"""
    try:
        response = requests.get(f"{XTTS_API_URL}/voices/active", timeout=5)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/voices/set-active")
async def proxy_set_active_voice(voice_filename: dict):
    """Aktif sesi değiştir (proxy)"""
    try:
        response = requests.post(
            f"{XTTS_API_URL}/voices/set-active",
            json=voice_filename,
            timeout=10
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/voices/upload")
async def proxy_upload_voice(file: bytes = None, name: str = None, description: str = None):
    """Ses yükle (proxy)"""
    try:
        # Bu endpoint'i doğrudan XTTS API'ye yönlendirmek için
        # multipart form data'yı forward etmemiz gerekir
        # Şimdilik direkt XTTS API'yi kullanın
        return {
            "message": "Upload için lütfen doğrudan XTTS API'yi kullanın",
            "url": f"{XTTS_API_URL}/voices/upload"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/cache/info")
async def proxy_cache_info():
    """Cache bilgisini getir (proxy)"""
    try:
        response = requests.get(f"{XTTS_API_URL}/cache/info", timeout=5)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print(f"🚀 XTTS Web UI başlatılıyor...")
    print(f"📡 XTTS API URL: {XTTS_API_URL}")
    print(f"🌐 Web UI: http://localhost:{PORT}")
    print(f"📋 Tarayıcıda açın: http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

