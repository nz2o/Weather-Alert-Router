from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from .db import init_db, SessionLocal
from .models import Alert, ApiKey
from .schemas import AlertIn, AlertOut, ApiKeyCreate
from .auth import verify_api_key, verify_admin
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, text
from starlette.responses import RedirectResponse
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
import json

app = FastAPI(title="Weather Alert Router")


@app.get("/spc_status")
def spc_status():
    db = SessionLocal()
    try:
        try:
            row = db.execute(text("SELECT source, last_run, last_success, convective_count, fire_count, message, updated_at FROM spc_ingest_status WHERE source='spc' LIMIT 1")).first()
        except Exception:
            return {"status": "unknown", "message": "spc_ingest_status table not present"}
        if not row:
            return {"status": "no-data"}
        return {
            "source": row.source,
            "last_run": row.last_run,
            "last_success": row.last_success,
            "convective_count": row.convective_count,
            "fire_count": row.fire_count,
            "message": row.message,
            "updated_at": row.updated_at,
        }
    finally:
        db.close()

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/alerts", response_class=JSONResponse)
def list_alerts():
    db = SessionLocal()
    try:
        table = Alert.__table__
        # Return selected columns including geometry as GeoJSON
        stmt = select(
            table.c.id,
            table.c.properties,
            func.ST_AsGeoJSON(table.c.geometry).label('geometry'),
            table.c.sent,
            table.c.effective,
            table.c.onset,
            table.c.expires,
            table.c.ends,
            table.c.status,
            table.c.message_type,
            table.c.category,
            table.c.severity,
            table.c.certainty,
            table.c.urgency,
            table.c.event,
            table.c.sender_name,
            table.c.headline,
            table.c.area_desc,
            table.c.description,
            table.c.instruction,
            table.c.response,
            table.c.geocode,
            table.c.geocode_ugc,
            table.c.geocode_same,
            table.c.parameters,
            table.c.parameters_awipsidentifier,
            table.c.parameters_blockchannel,
            table.c.parameters_cmamlongtext,
            table.c.parameters_cmamtext,
            table.c.parameters_eas_org,
            table.c.parameters_eventendingtime,
            table.c.parameters_eventmotiondescription,
            table.c.parameters_expiredreferences,
            table.c.parameters_hailthreat,
            table.c.parameters_maxhailsize,
            table.c.parameters_maxwindgust,
            table.c.parameters_nwsheadline,
            table.c.parameters_tornadodetection,
            table.c.parameters_vtec,
            table.c.parameters_waterspoutdetection,
            table.c.parameters_weahandling,
            table.c.parameters_windthreat,
            table.c.parameters_wmoidentifier,
            table.c.affected_zones,
            table.c.references,
        )
        try:
            rows = db.execute(stmt).all()
        except Exception:
            # If the extracted columns don't exist yet (older DB), fall back
            # to a minimal query to avoid crashing the app.
            fallback = select(table.c.id, table.c.properties, func.ST_AsGeoJSON(table.c.geometry).label('geometry'))
            rows = db.execute(fallback).all()
        out = []
        for r in rows:
            geom = r.geometry
            if geom is not None:
                try:
                    geom = json.loads(geom)
                except Exception:
                    pass
            out.append({
                "id": r.id,
                "properties": r.properties,
                "geometry": geom,
                "sent": r.sent,
                "effective": r.effective,
                "onset": r.onset,
                "expires": r.expires,
                "ends": r.ends,
                "status": r.status,
                "messageType": r.message_type,
                "category": r.category,
                "severity": r.severity,
                "certainty": r.certainty,
                "urgency": r.urgency,
                "event": r.event,
                "senderName": r.sender_name,
                "headline": r.headline,
                "areaDesc": r.area_desc,
                "description": r.description,
                "instruction": r.instruction,
                "response": r.response,
                "geocode": r.geocode,
                "geocode_ugc": r.geocode_ugc,
                "geocode_same": r.geocode_same,
                "parameters": r.parameters,
                "parameters_awipsidentifier": r.parameters_awipsidentifier,
                "parameters_blockchannel": r.parameters_blockchannel,
                "parameters_cmamlongtext": r.parameters_cmamlongtext,
                "parameters_cmamtext": r.parameters_cmamtext,
                "parameters_eas_org": r.parameters_eas_org,
                "parameters_eventendingtime": r.parameters_eventendingtime,
                "parameters_eventmotiondescription": r.parameters_eventmotiondescription,
                "parameters_expiredreferences": r.parameters_expiredreferences,
                "parameters_hailthreat": r.parameters_hailthreat,
                "parameters_maxhailsize": r.parameters_maxhailsize,
                "parameters_maxwindgust": r.parameters_maxwindgust,
                "parameters_nwsheadline": r.parameters_nwsheadline,
                "parameters_tornadodetection": r.parameters_tornadodetection,
                "parameters_vtec": r.parameters_vtec,
                "parameters_waterspoutdetection": r.parameters_waterspoutdetection,
                "parameters_weahandling": r.parameters_weahandling,
                "parameters_windthreat": r.parameters_windthreat,
                "parameters_wmoidentifier": r.parameters_wmoidentifier,
                "affectedZones": r.affected_zones,
                "references": r.references,
            })
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
