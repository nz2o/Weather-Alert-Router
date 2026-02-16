import os
import time
import json
import requests
from .db import SessionLocal
from .models import Alert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

NWS_URL = "https://api.weather.gov/alerts"


def _normalize_id(aid: str) -> str:
    if not aid:
        return aid
    # Remove the common NWS URL prefix if present
    prefix = "https://api.weather.gov/alerts/"
    if aid.startswith(prefix):
        return aid[len(prefix):]
    return aid


def fetch_and_store(limit=100):
    """Fetch alerts from NWS and upsert into Postgres alerts table.

    - Strip the 'https://api.weather.gov/alerts/' prefix from IDs.
    - Convert GeoJSON geometry to PostGIS geometry using ST_GeomFromGeoJSON
      and only update geometry on conflict when a geometry is provided.
    """
    resp = requests.get(NWS_URL, params={"limit": limit}, headers={"User-Agent": "weather-alert-router/1.0"})
    resp.raise_for_status()
    data = resp.json()
    features = data.get('features', [])
    db = SessionLocal()
    try:
        table = Alert.__table__
        for f in features:
            raw_id = f.get('id') or f.get('properties', {}).get('id')
            aid = _normalize_id(raw_id)
            if not aid:
                continue
            properties = f.get('properties') or {}
            geom = f.get('geometry')

            # Build geometry expression only if geometry exists
            geom_expr = None
            if geom:
                geom_json = json.dumps(geom)
                geom_expr = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_json), 4326)

            # Prepare insert statement with optional geometry
            if geom_expr is not None:
                stmt = pg_insert(table).values(id=aid, properties=properties, geometry=geom_expr)
            else:
                stmt = pg_insert(table).values(id=aid, properties=properties)

            # On conflict, update properties and update geometry only when provided
            update_dict = { 'properties': stmt.excluded.properties }
            if geom_expr is not None:
                update_dict['geometry'] = stmt.excluded.geometry

            stmt = stmt.on_conflict_do_update(
                index_elements=[table.c.id],
                set_=update_dict
            )
            try:
                db.execute(stmt)
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


def run_polling():
    """Run fetch loop. Configure with environment variables:

    - `POLL_ENABLED` (set to '1' to run continuously)
    - `POLL_INTERVAL_SECONDS` (defaults to 300 seconds)
    - `POLL_LIMIT` (number of records to request per fetch, default 100)
    """
    poll_enabled = os.getenv('POLL_ENABLED', '0') in ('1', 'true', 'True')
    interval = int(os.getenv('POLL_INTERVAL_SECONDS', '300'))
    limit = int(os.getenv('POLL_LIMIT', '100'))

    # One-shot run
    fetch_and_store(limit=limit)

    if poll_enabled:
        while True:
            time.sleep(interval)
            fetch_and_store(limit=limit)


if __name__ == '__main__':
    run_polling()
