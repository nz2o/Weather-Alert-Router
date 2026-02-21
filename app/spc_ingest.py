"""SPC outlook poller.

Usage:
  - Run once: `python -m app.spc_ingest --once`
  - Run as continuous service (polls each top-of-hour): `python -m app.spc_ingest --loop`

The script will:
 - Fetch the configured SPC GeoJSON URLs
 - Save a copy into `examples/spc/` (filename derived from URL)
 - Upsert the payload into the Postgres tables created by `db_init/03_spc_outlooks.sql`

Note: to run continuously in Docker, add a service to docker-compose that runs
`python -m app.spc_ingest --loop`.
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from sqlalchemy import text

from .db import engine, load_dotenv

# Ensure examples/spc directory exists
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples" / "spc"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# List of SPC GeoJSON URLs to poll (convective outlooks + experiments + fire)
SPC_URLS = [
    # Day 1
    ("day1otlk_cat_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson", "day1_cat_nolyr"),
    ("day1otlk_cat_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.lyr.geojson", "day1_cat_lyr"),
    ("day1otlk_torn_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_torn.nolyr.geojson", "day1_torn_nolyr"),
    ("day1otlk_torn_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_torn.lyr.geojson", "day1_torn_lyr"),
    ("day1otlk_sigtorn_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sigtorn.nolyr.geojson", "day1_sigtorn_nolyr"),
    ("day1otlk_sigtorn_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sigtorn.lyr.geojson", "day1_sigtorn_lyr"),
    ("day1otlk_hail_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_hail.nolyr.geojson", "day1_hail_nolyr"),
    ("day1otlk_hail_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_hail.lyr.geojson", "day1_hail_lyr"),
    ("day1otlk_sighail_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sighail.nolyr.geojson", "day1_sighail_nolyr"),
    ("day1otlk_sighail_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sighail.lyr.geojson", "day1_sighail_lyr"),
    ("day1otlk_wind_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_wind.nolyr.geojson", "day1_wind_nolyr"),
    ("day1otlk_wind_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_wind.lyr.geojson", "day1_wind_lyr"),
    ("day1otlk_sigwind_nolyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sigwind.nolyr.geojson", "day1_sigwind_nolyr"),
    ("day1otlk_sigwind_lyr", "https://www.spc.noaa.gov/products/outlook/day1otlk_sigwind.lyr.geojson", "day1_sigwind_lyr"),
    # Day 2 (examples)
    ("day2otlk_cat_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_cat.nolyr.geojson", "day2_cat_nolyr"),
    ("day2otlk_cat_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_cat.lyr.geojson", "day2_cat_lyr"),
    ("day2otlk_torn_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_torn.nolyr.geojson", "day2_torn_nolyr"),
    ("day2otlk_torn_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_torn.lyr.geojson", "day2_torn_lyr"),
    ("day2otlk_sigtorn_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sigtorn.nolyr.geojson", "day2_sigtorn_nolyr"),
    ("day2otlk_sigtorn_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sigtorn.lyr.geojson", "day2_sigtorn_lyr"),
    ("day2otlk_hail_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_hail.nolyr.geojson", "day2_hail_nolyr"),
    ("day2otlk_hail_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_hail.lyr.geojson", "day2_hail_lyr"),
    ("day2otlk_sighail_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sighail.nolyr.geojson", "day2_sighail_nolyr"),
    ("day2otlk_sighail_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sighail.lyr.geojson", "day2_sighail_lyr"),
    ("day2otlk_wind_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_wind.nolyr.geojson", "day2_wind_nolyr"),
    ("day2otlk_wind_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_wind.lyr.geojson", "day2_wind_lyr"),
    ("day2otlk_sigwind_nolyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sigwind.nolyr.geojson", "day2_sigwind_nolyr"),
    ("day2otlk_sigwind_lyr", "https://www.spc.noaa.gov/products/outlook/day2otlk_sigwind.lyr.geojson", "day2_sigwind_lyr"),
    # Day 3 examples
    ("day3otlk_cat_nolyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_cat.nolyr.geojson", "day3_cat_nolyr"),
    ("day3otlk_cat_lyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_cat.lyr.geojson", "day3_cat_lyr"),
    ("day3otlk_prob_nolyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_prob.nolyr.geojson", "day3_prob_nolyr"),
    ("day3otlk_prob_lyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_prob.lyr.geojson", "day3_prob_lyr"),
    ("day3otlk_sigprob_nolyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_sigprob.nolyr.geojson", "day3_sigprob_nolyr"),
    ("day3otlk_sigprob_lyr", "https://www.spc.noaa.gov/products/outlook/day3otlk_sigprob.lyr.geojson", "day3_sigprob_lyr"),
    # Day 4-8 probs (examples for day4)
    ("day4prob_nolyr", "https://www.spc.noaa.gov/products/exper/day4-8/day4prob.nolyr.geojson", "day4_prob_nolyr"),
    ("day4prob_lyr", "https://www.spc.noaa.gov/products/exper/day4-8/day4prob.lyr.geojson", "day4_prob_lyr"),
    # Fire weather examples (day1/day2)
    ("day1fw_dryt_nolyr", "https://www.spc.noaa.gov/products/fire_wx/day1fw_dryt.nolyr.geojson", "day1fw_dryt_nolyr"),
    ("day1fw_dryt_lyr", "https://www.spc.noaa.gov/products/fire_wx/day1fw_dryt.lyr.geojson", "day1fw_dryt_lyr"),
    ("day1fw_windrh_nolyr", "https://www.spc.noaa.gov/products/fire_wx/day1fw_windrh.nolyr.geojson", "day1fw_windrh_nolyr"),
    ("day1fw_windrh_lyr", "https://www.spc.noaa.gov/products/fire_wx/day1fw_windrh.lyr.geojson", "day1fw_windrh_lyr"),
    ("day2fw_dryt_nolyr", "https://www.spc.noaa.gov/products/fire_wx/day2fw_dryt.nolyr.geojson", "day2fw_dryt_nolyr"),
    ("day2fw_dryt_lyr", "https://www.spc.noaa.gov/products/fire_wx/day2fw_dryt.lyr.geojson", "day2fw_dryt_lyr"),
]


def save_example(name: str, url: str, content: bytes):
    fname = EXAMPLES_DIR / f"{name}.geojson"
    with open(fname, "wb") as f:
        f.write(content)


def upsert_convective(product: str, url: str, payload: dict):
    stmt = text(
        """
        INSERT INTO convective_outlooks (product, url, payload, fetched_hour)
        VALUES (:product, :url, :payload, date_trunc('hour', now()))
        ON CONFLICT (url, fetched_hour) DO UPDATE
          SET payload = EXCLUDED.payload
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"product": product, "url": url, "payload": json.dumps(payload)})


def upsert_fire(product: str, url: str, payload: dict):
    stmt = text(
        """
        INSERT INTO fire_outlooks (product, url, payload, fetched_hour)
        VALUES (:product, :url, :payload, date_trunc('hour', now()))
        ON CONFLICT (url, fetched_hour) DO UPDATE
          SET payload = EXCLUDED.payload
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"product": product, "url": url, "payload": json.dumps(payload)})


def fetch_and_store(name: str, url: str, product: str):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        content = r.content
        # Save example payload
        save_example(name, url, content)
        # Parse JSON
        payload = r.json()
        # Decide table by path
        if "/fire_wx/" in url or "fire_wx" in name:
            upsert_fire(product, url, payload)
        else:
            upsert_convective(product, url, payload)
        print(f"Stored {name} -> {url}")
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")


def fetch_all_once():
    for name, url, product in SPC_URLS:
        fetch_and_store(name, url, product)


def sleep_until_top_of_hour():
    now = datetime.utcnow()
    # Next top of hour
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    delta = (next_hour - now).total_seconds()
    print(f"Sleeping {int(delta)}s until next top-of-hour: {next_hour.isoformat()} UTC")
    time.sleep(delta)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run continuously at top-of-hour")
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    args = parser.parse_args()

    if args.once:
        fetch_all_once()
        return

    if args.loop:
        # Align to top of hour then loop
        print("SPC poller: running in loop mode (top-of-hour fetches)")
        # On start, fetch immediately
        fetch_all_once()
        while True:
            sleep_until_top_of_hour()
            fetch_all_once()


if __name__ == "__main__":
    main()
