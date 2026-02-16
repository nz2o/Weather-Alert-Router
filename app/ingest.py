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
        _process_features(features, db)
    finally:
        db.close()


def _process_features(features, db):
    """Process a list of GeoJSON Feature objects and upsert them into DB.

    This centralizes the upsert logic so it can be used for live fetches
    and loading example snapshots.
    """
    table = Alert.__table__
    for f in features:
        raw_id = f.get('id') or f.get('properties', {}).get('id')
        aid = _normalize_id(raw_id)
        if not aid:
            continue
        properties = f.get('properties') or {}
        geom = f.get('geometry')

        geom_expr = None
        if geom:
            geom_json = json.dumps(geom)
            geom_expr = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_json), 4326)

        # Map first-level properties into individual columns when available
        sent = properties.get('sent')
        effective = properties.get('effective')
        onset = properties.get('onset')
        expires = properties.get('expires')
        ends = properties.get('ends')

        status = properties.get('status')
        message_type = properties.get('messageType')
        category = properties.get('category')
        severity = properties.get('severity')
        certainty = properties.get('certainty')
        urgency = properties.get('urgency')

        event = properties.get('event')
        sender_name = properties.get('senderName')

        headline = properties.get('headline')
        area_desc = properties.get('areaDesc')
        description = properties.get('description')
        instruction = properties.get('instruction')
        response = properties.get('response')

        geocode = properties.get('geocode')
        geocode_ugc = None
        geocode_same = None
        if isinstance(geocode, dict):
            geocode_ugc = geocode.get('UGC')
            geocode_same = geocode.get('SAME')
        parameters = properties.get('parameters')
        affected_zones = properties.get('affectedZones')
        references = properties.get('references')

        values = dict(
            id=aid,
            properties=properties,
            sent=sent,
            effective=effective,
            onset=onset,
            expires=expires,
            ends=ends,
            status=status,
            message_type=message_type,
            category=category,
            severity=severity,
            certainty=certainty,
            urgency=urgency,
            event=event,
            sender_name=sender_name,
            headline=headline,
            area_desc=area_desc,
            description=description,
            instruction=instruction,
            response=response,
            geocode=geocode,
            geocode_ugc=geocode_ugc,
            geocode_same=geocode_same,
            parameters=parameters,
            affected_zones=affected_zones,
            references=references,
        )

        if geom_expr is not None:
            values['geometry'] = geom_expr

        stmt = pg_insert(table).values(**values)

        # Build update dict; use excluded for columns so upsert updates fields
        update_dict = {c: getattr(stmt.excluded, c) for c in [
            'properties', 'sent', 'effective', 'onset', 'expires', 'ends',
            'status', 'message_type', 'category', 'severity', 'certainty', 'urgency',
            'event', 'sender_name', 'headline', 'area_desc', 'description',
            'instruction', 'response', 'geocode', 'parameters', 'affected_zones', 'references'
        ]}
        if geom_expr is not None:
            update_dict['geometry'] = stmt.excluded.geometry

        # include split geocode fields
        update_dict['geocode_ugc'] = stmt.excluded.geocode_ugc
        update_dict['geocode_same'] = stmt.excluded.geocode_same

        # map parameter keys into per-parameter columns (JSONB)
        if parameters and isinstance(parameters, dict):
            # Known parameter keys — ensure these names match model columns
            for pk in [
                'AWIPSidentifier','BLOCKCHANNEL','CMAMlongtext','CMAMtext','EAS-ORG',
                'eventEndingTime','eventMotionDescription','expiredReferences','hailThreat',
                'maxHailSize','maxWindGust','NWSheadline','tornadoDetection','VTEC',
                'waterspoutDetection','WEAHandling','windThreat','WMOidentifier'
            ]:
                if pk in parameters:
                    col = 'parameters_' + ''.join([c.lower() if c.isalnum() else '_' for c in pk])
                    update_dict[col] = getattr(stmt.excluded, col)

        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.id],
            set_=update_dict
        )
        try:
            db.execute(stmt)
            db.commit()
        except Exception:
            db.rollback()


def load_example_and_store():
    """Load example JSON from the `examples/alerts_snapshot.json` file and process it.

    Controlled by the `LOAD_EXAMPLE_JSON` environment variable.
    """
    load_example = os.getenv('LOAD_EXAMPLE_JSON', '0') in ('1', 'true', 'True')
    if not load_example:
        return

    path = os.getenv('LOAD_EXAMPLE_JSON_PATH', 'examples/alerts_snapshot.json')
    if not os.path.exists(path):
        return

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception:
        return

    features = data.get('features', []) if isinstance(data, dict) else []
    if not features:
        return

    db = SessionLocal()
    try:
        _process_features(features, db)
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

    # Optionally load example snapshot first (useful for dev/testing)
    load_example_and_store()

    # One-shot run against the live API
    fetch_and_store(limit=limit)

    if poll_enabled:
        while True:
            time.sleep(interval)
            fetch_and_store(limit=limit)


if __name__ == '__main__':
    run_polling()
