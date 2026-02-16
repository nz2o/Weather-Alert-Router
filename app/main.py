from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from .db import init_db, SessionLocal
from .models import Alert, ApiKey
from .schemas import AlertIn, AlertOut, ApiKeyCreate
from .auth import verify_api_key, verify_admin
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from starlette.responses import RedirectResponse

app = FastAPI(title="Weather Alert Router")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/alerts", response_class=JSONResponse)
def list_alerts():
    db = SessionLocal()
    try:
        alerts = db.execute(select(Alert)).scalars().all()
        out = [{"id": a.id, "properties": a.properties} for a in alerts]
        return out
    finally:
        db.close()


@app.post("/alerts", dependencies=[Depends(verify_api_key)])
def post_alert(alert: AlertIn):
    db = SessionLocal()
    try:
        a = Alert(id=alert.id, properties=alert.properties)
        db.add(a)
        db.commit()
        return {"status": "ok"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alert already exists")
    finally:
        db.close()


@app.post("/apikeys", dependencies=[Depends(verify_api_key)])
def create_apikey(data: ApiKeyCreate):
    db = SessionLocal()
    import secrets
    key = secrets.token_urlsafe(32)
    k = ApiKey(key=key, owner=data.owner)
    db.add(k)
    db.commit()
    db.close()
    return {"key": key}


# Admin UI for API key management (protected by ADMIN_KEY via X-Admin-Key header)
@app.get("/admin/apikeys", response_class=HTMLResponse, dependencies=[Depends(verify_admin)])
def admin_list(request: Request):
    db = SessionLocal()
    try:
        keys = db.query(ApiKey).order_by(ApiKey.id.desc()).all()
        return templates.TemplateResponse("apikeys.html", {"request": request, "keys": keys})
    finally:
        db.close()


@app.post("/admin/apikeys/create", response_class=HTMLResponse, dependencies=[Depends(verify_admin)])
def admin_create(request: Request, owner: str = Form(None)):
    db = SessionLocal()
    import secrets
    key = secrets.token_urlsafe(32)
    k = ApiKey(key=key, owner=owner)
    db.add(k)
    db.commit()
    try:
        return templates.TemplateResponse("create_result.html", {"request": request, "key": key, "owner": owner})
    finally:
        db.close()


@app.post("/admin/apikeys/revoke", response_class=HTMLResponse, dependencies=[Depends(verify_admin)])
def admin_revoke(request: Request, key_id: int = Form(...)):
    db = SessionLocal()
    try:
        k = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if k:
            k.active = 0
            db.add(k)
            db.commit()
        return RedirectResponse(url="/admin/apikeys", status_code=303)
    finally:
        db.close()
