import os
import time
import requests
from .db import SessionLocal
from .models import Alert
from sqlalchemy.dialects.postgresql import insert as pg_insert

NWS_URL = "https://api.weather.gov/alerts"


def fetch_and_store(limit=100):
    """Fetch alerts from NWS and upsert into Postgres alerts table."""
    resp = requests.get(NWS_URL, params={"limit": limit}, headers={"User-Agent": "weather-alert-router/1.0"})
    resp.raise_for_status()
    data = resp.json()
    features = data.get('features', [])
    db = SessionLocal()
    try:
        table = Alert.__table__
        for f in features:
            aid = f.get('id') or f.get('properties', {}).get('id')
            if not aid:
                continue
            properties = f.get('properties') or {}
            stmt = pg_insert(table).values(id=aid, properties=properties)
            stmt = stmt.on_conflict_do_update(
                index_elements=[table.c.id],
                set_={
                    'properties': stmt.excluded.properties
                }
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
