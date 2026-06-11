import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Form, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

import rag
import ingest as ing

# ---------- Sabitler ----------

TENANTS_FILE    = Path("tenants/tenants.json")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PASSWORD", "admin123")
UNANSWERED_MARK = "belgede bilgi bulunamadı"

DEFAULT_SETTINGS = {
    "bot_name": "Destek Asistanı",
    "welcome_message": "Merhaba! Size nasıl yardımcı olabilirim?",
    "color": "#1a1a2e",
    "icon": "💬",
}

_valid_sessions: set = set()

# ---------- Yardımcı Fonksiyonlar ----------

def _tenant_dir(tenant_id: str) -> Path:
    d = Path("tenants") / tenant_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def _docs_dir(tenant_id: str) -> Path:
    d = _tenant_dir(tenant_id) / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _tenant_file(tenant_id: str, filename: str) -> Path:
    return _tenant_dir(tenant_id) / filename

def _load_tenants() -> dict:
    TENANTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TENANTS_FILE.exists():
        return json.loads(TENANTS_FILE.read_text())
    return {}

def _save_tenants(data: dict):
    TENANTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def _require_tenant(tenant_id: str):
    if tenant_id not in _load_tenants():
        raise HTTPException(status_code=404, detail=f"'{tenant_id}' adlı müşteri bulunamadı.")

def _log_question(tenant_id: str, question: str, answer: str):
    f = _tenant_file(tenant_id, "questions_log.json")
    entries = json.loads(f.read_text()) if f.exists() else []
    entries.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "answered": UNANSWERED_MARK not in answer.lower(),
    })
    f.write_text(json.dumps(entries, ensure_ascii=False, indent=2))

def _load_settings(tenant_id: str) -> dict:
    f = _tenant_file(tenant_id, "settings.json")
    if f.exists():
        return {**DEFAULT_SETTINGS, **json.loads(f.read_text())}
    return DEFAULT_SETTINGS.copy()

def _is_authenticated(request: Request) -> bool:
    return request.cookies.get("session") in _valid_sessions

# ---------- App ----------

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- Auth ----------

@app.get("/login")
def serve_login():
    return FileResponse("login.html")

@app.post("/login")
async def do_login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return RedirectResponse("/login?error=1", status_code=303)
    token = secrets.token_hex(32)
    _valid_sessions.add(token)
    response = RedirectResponse("/superadmin", status_code=303)
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return response

@app.get("/logout")
def do_logout(request: Request):
    _valid_sessions.discard(request.cookies.get("session"))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response

# ---------- Sayfalar ----------

@app.get("/")
def serve_ui():
    return FileResponse("index.html")

@app.get("/superadmin")
def serve_superadmin(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return FileResponse("superadmin.html")

@app.get("/admin")
def serve_admin(request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    _require_tenant(tenant)
    return FileResponse("admin.html")

@app.get("/widget.js")
def serve_widget():
    return FileResponse("widget.js", media_type="application/javascript")

# ---------- Tenant Yönetimi ----------

@app.get("/tenants")
def list_tenants(request: Request):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    tenants = _load_tenants()
    result = []
    for tid, info in tenants.items():
        docs = ing.list_documents(tid)
        result.append({
            "id":         tid,
            "name":       info.get("name", tid),
            "created_at": info.get("created_at", ""),
            "doc_count":  len(docs),
        })
    return result

@app.post("/tenants")
def create_tenant(request: Request, data: dict):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Müşteri adı boş olamaz.")
    tid = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())[:40]
    tenants = _load_tenants()
    if tid in tenants:
        raise HTTPException(status_code=409, detail=f"'{tid}' ID zaten kullanımda.")
    tenants[tid] = {"name": name, "created_at": datetime.now().isoformat(timespec="seconds")}
    _save_tenants(tenants)
    _docs_dir(tid)
    return {"id": tid, "name": name}

@app.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, request: Request):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    tenants = _load_tenants()
    if tenant_id not in tenants:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı.")
    del tenants[tenant_id]
    _save_tenants(tenants)
    ing.delete_tenant_collection(tenant_id)
    import shutil
    shutil.rmtree(_tenant_dir(tenant_id), ignore_errors=True)
    return {"ok": True}

# ---------- Chat ----------

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[HistoryMessage] = []
    tenant_id: str = "default"

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    history = [{"role": m.role, "content": m.content} for m in req.history]
    reply   = rag.answer(req.message, history, tenant_id=req.tenant_id)
    _log_question(req.tenant_id, req.message, reply)
    return ChatResponse(reply=reply)

# ---------- Belgeler ----------

@app.get("/documents")
def list_documents(request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    _require_tenant(tenant)
    return ing.list_documents(tenant)

@app.post("/documents/upload")
async def upload_document(request: Request, tenant: str = Query(...), file: UploadFile = File(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    _require_tenant(tenant)
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyası yüklenebilir.")
    pdf_path = _docs_dir(tenant) / file.filename
    pdf_path.write_bytes(await file.read())
    try:
        added = ing.ingest_pdf(pdf_path, tenant)
    except ValueError as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    if added == 0:
        return {"message": "Bu belge zaten indeksli.", "chunks": 0}
    return {"message": f"{file.filename} başarıyla yüklendi.", "chunks": added}

@app.delete("/documents/{filename}")
def delete_document(filename: str, request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    _require_tenant(tenant)
    deleted = ing.delete_pdf(filename, tenant)
    ((_docs_dir(tenant)) / filename).unlink(missing_ok=True)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Belge bulunamadı.")
    return {"message": f"{filename} silindi.", "chunks_removed": deleted}

# ---------- Feedback ----------

class FeedbackRequest(BaseModel):
    question: str
    answer: str
    rating: str
    tenant_id: str = "default"

@app.post("/feedback")
def save_feedback(req: FeedbackRequest):
    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Geçersiz puan.")
    f = _tenant_file(req.tenant_id, "feedback.json")
    entries = json.loads(f.read_text()) if f.exists() else []
    entries.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": req.question,
        "answer":   req.answer,
        "rating":   req.rating,
    })
    f.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    return {"ok": True}

@app.get("/feedback")
def get_feedback(request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    f = _tenant_file(tenant, "feedback.json")
    return json.loads(f.read_text()) if f.exists() else []

# ---------- Ayarlar ----------

class SettingsRequest(BaseModel):
    bot_name: str
    welcome_message: str
    color: str
    icon: str

@app.get("/settings")
def get_settings(tenant: str = Query(default="default")):
    return _load_settings(tenant)

@app.post("/settings")
def save_settings(req: SettingsRequest, request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    f = _tenant_file(tenant, "settings.json")
    f.write_text(json.dumps(req.dict(), ensure_ascii=False, indent=2))
    return {"ok": True}

# ---------- Müşteri Geri Bildirimleri ----------

class CustomerFeedbackRequest(BaseModel):
    text: str
    tenant_id: str = "default"

@app.post("/customer-feedback")
def save_customer_feedback(req: CustomerFeedbackRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Geri bildirim boş olamaz.")
    feedback_type = rag.classify_feedback(req.text)
    f = _tenant_file(req.tenant_id, "customer_feedback.json")
    entries = json.loads(f.read_text()) if f.exists() else []
    entries.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "text":      req.text,
        "type":      feedback_type,
    })
    f.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    return {"ok": True, "type": feedback_type}

@app.get("/customer-feedback")
def get_customer_feedback(request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    f = _tenant_file(tenant, "customer_feedback.json")
    return json.loads(f.read_text()) if f.exists() else []

# ---------- Analitik ----------

@app.get("/analytics")
def get_analytics(request: Request, tenant: str = Query(...)):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    f = _tenant_file(tenant, "questions_log.json")
    if not f.exists():
        return {"top_questions": [], "unanswered": [], "daily_activity": []}
    entries = json.loads(f.read_text())
    counts: dict = {}
    for e in entries:
        q = e["question"].strip()
        counts[q] = counts.get(q, 0) + 1
    top_questions = sorted(
        [{"question": q, "count": c} for q, c in counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:10]
    unanswered = [
        {"question": e["question"], "timestamp": e["timestamp"]}
        for e in entries if not e.get("answered", True)
    ][-20:]
    day_counts: dict = {}
    for e in entries:
        day = e["timestamp"][:10]
        day_counts[day] = day_counts.get(day, 0) + 1
    daily_activity = [
        {"date": d, "count": c}
        for d, c in sorted(day_counts.items())[-7:]
    ]
    return {"top_questions": top_questions, "unanswered": unanswered, "daily_activity": daily_activity}
