import os
import time
import hmac
import hashlib
import base64
from fastapi import FastAPI, Request, Form, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from .db import SessionLocal
from .models import ApiKey


templates = Jinja2Templates(directory="app/templates_admin")
app = FastAPI(title="Admin Client UI")


def make_csrf_token(secret: str, ttl_seconds: int = 300) -> str:
    ts = str(int(time.time()))
    mac = hmac.new(secret.encode('utf-8'), ts.encode('utf-8'), hashlib.sha256).digest()
    b = base64.urlsafe_b64encode(mac).decode('utf-8').rstrip('=')
    return f"{b}|{ts}"


def verify_csrf_token(token: str, secret: str, max_age: int = 300) -> bool:
    try:
        sig_b64, ts_s = token.split('|', 1)
        ts = int(ts_s)
    except Exception:
        return False
    if abs(int(time.time()) - ts) > max_age:
        return False
    expected = hmac.new(secret.encode('utf-8'), ts_s.encode('utf-8'), hashlib.sha256).digest()
    expected_b64 = base64.urlsafe_b64encode(expected).decode('utf-8').rstrip('=')
    return hmac.compare_digest(expected_b64, sig_b64.rstrip('='))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Generate a short-lived CSRF token for the page.
    secret = os.getenv('CSRF_SECRET') or os.getenv('ADMIN_KEY') or 'dev-secret'
    token = make_csrf_token(secret)
    return templates.TemplateResponse("admin_client.html", {"request": request, "csrf_token": token})


@app.get('/api/apikeys')
def api_list_keys():
    db = SessionLocal()
    try:
        keys = db.query(ApiKey).order_by(ApiKey.id.desc()).all()
        out = [{"id": k.id, "owner": k.owner, "active": bool(k.active)} for k in keys]
        return JSONResponse(out)
    finally:
        db.close()


@app.post('/api/apikeys/create')
def api_create_key(owner: str = Form(None), x_csrf_token: str = Header(None)):
    secret = os.getenv('CSRF_SECRET') or os.getenv('ADMIN_KEY') or 'dev-secret'
    if not x_csrf_token:
        raise HTTPException(status_code=401, detail='Missing CSRF token')
    if not verify_csrf_token(x_csrf_token, secret):
        raise HTTPException(status_code=401, detail='Invalid CSRF token')
    import secrets
    key = secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        k = ApiKey(key=key, owner=owner)
        db.add(k)
        db.commit()
        return JSONResponse({"key": key, "owner": owner})
    finally:
        db.close()


@app.post('/api/apikeys/revoke')
def api_revoke_key(key_id: int = Form(...), x_csrf_token: str = Header(None)):
    secret = os.getenv('CSRF_SECRET') or os.getenv('ADMIN_KEY') or 'dev-secret'
    if not x_csrf_token:
        raise HTTPException(status_code=401, detail='Missing CSRF token')
    if not verify_csrf_token(x_csrf_token, secret):
        raise HTTPException(status_code=401, detail='Invalid CSRF token')
    db = SessionLocal()
    try:
        k = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if k:
            k.active = 0
            db.add(k)
            db.commit()
        return JSONResponse({"revoked": True})
    finally:
        db.close()
