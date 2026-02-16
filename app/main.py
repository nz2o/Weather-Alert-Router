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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
import json

app = FastAPI(title="Weather Alert Router")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/alerts", response_class=JSONResponse)
def list_alerts():
    db = SessionLocal()
    try:
        table = Alert.__table__
        # Return stored geometry as GeoJSON (or null) so callers can inspect it
        stmt = select(table.c.id, table.c.properties, func.ST_AsGeoJSON(table.c.geometry).label('geometry'))
        rows = db.execute(stmt).all()
        out = []
        for r in rows:
            geom = r.geometry
            # ST_AsGeoJSON returns a JSON string; parse it back to JSON if present
            if geom is not None:
                try:
                    geom = json.loads(geom)
                except Exception:
                    # leave as-is (string) if parsing fails
                    pass
            out.append({"id": r.id, "properties": r.properties, "geometry": geom})
        return out
    finally:
        db.close()


@app.post("/alerts", dependencies=[Depends(verify_api_key)])
def post_alert(alert: AlertIn):
    db = SessionLocal()
    try:
        table = Alert.__table__
        # Normalize id (strip NWS prefix if present)
        aid = alert.id
        prefix = "https://api.weather.gov/alerts/"
        if aid and aid.startswith(prefix):
            aid = aid[len(prefix):]

        properties = alert.properties or {}
        geom = getattr(alert, 'geometry', None)
        geom_expr = None
        if geom:
            geom_json = json.dumps(geom)
            geom_expr = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_json), 4326)

        if geom_expr is not None:
            stmt = pg_insert(table).values(id=aid, properties=properties, geometry=geom_expr)
        else:
            stmt = pg_insert(table).values(id=aid, properties=properties)

        update_dict = { 'properties': stmt.excluded.properties }
        if geom_expr is not None:
            update_dict['geometry'] = stmt.excluded.geometry

        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.id],
            set_=update_dict
        )

        db.execute(stmt)
        db.commit()
        return {"status": "ok"}
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
