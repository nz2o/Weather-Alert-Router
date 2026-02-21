"""SPC outlook poller.

Run once: `python -m app.spc_ingest --once`
Run in loop: `python -m app.spc_ingest --loop`

This module fetches SPC GeoJSON products, saves examples to `examples/spc/`,
and upserts each GeoJSON Feature as a single row in the *_outlooks tables.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import sqlalchemy as sa
from sqlalchemy import exc, text, bindparam

from .db import engine, init_db, load_dotenv


# Ensure examples/spc directory exists
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples" / "spc"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


# Minimal list of SPC endpoints (kept short here; original repo holds full list)
SPC_FILES = [
    "day1fw_dryt_lyr.geojson",
    "day1fw_dryt_nolyr.geojson",
    "day1fw_windrh_lyr.geojson",
    "day1fw_windrh_nolyr.geojson",

    "day1otlk_cat_lyr.geojson",
    "day1otlk_cat_nolyr.geojson",
    "day1otlk_hail_lyr.geojson",
    "day1otlk_hail_nolyr.geojson",
    "day1otlk_sighail_lyr.geojson",
    "day1otlk_sighail_nolyr.geojson",
    "day1otlk_sigtorn_lyr.geojson",
    "day1otlk_sigtorn_nolyr.geojson",
    "day1otlk_sigwind_lyr.geojson",
    "day1otlk_sigwind_nolyr.geojson",
    "day1otlk_torn_lyr.geojson",
    "day1otlk_torn_nolyr.geojson",
    "day1otlk_wind_lyr.geojson",
    "day1otlk_wind_nolyr.geojson",

    "day2fw_dryt_lyr.geojson",
    "day2fw_dryt_nolyr.geojson",

    "day2otlk_cat_lyr.geojson",
    "day2otlk_cat_nolyr.geojson",
    "day2otlk_hail_lyr.geojson",
    "day2otlk_hail_nolyr.geojson",
    "day2otlk_sighail_lyr.geojson",
    "day2otlk_sighail_nolyr.geojson",
    "day2otlk_sigtorn_lyr.geojson",
    "day2otlk_sigtorn_nolyr.geojson",
    "day2otlk_sigwind_lyr.geojson",
    "day2otlk_sigwind_nolyr.geojson",
    "day2otlk_torn_lyr.geojson",
    "day2otlk_torn_nolyr.geojson",
    "day2otlk_wind_lyr.geojson",
    "day2otlk_wind_nolyr.geojson",

    "day3otlk_cat_lyr.geojson",
    "day3otlk_cat_nolyr.geojson",
    "day3otlk_prob_lyr.geojson",
    "day3otlk_prob_nolyr.geojson",
    "day3otlk_sigprob_lyr.geojson",
    "day3otlk_sigprob_nolyr.geojson",

    "day4prob_lyr.geojson",
    "day4prob_nolyr.geojson",
]


def _file_to_tuple(fname: str):
    # determine product category
    base = fname
    if base.startswith("day1fw") or base.startswith("day2fw"):
        category = "fire_wx"
    else:
        category = "outlook"

    if base.endswith("_nolyr.geojson"):
        urlname = base.replace("_nolyr.geojson", ".nolyr.geojson")
    elif base.endswith("_lyr.geojson"):
        urlname = base.replace("_lyr.geojson", ".lyr.geojson")
    else:
        urlname = base

    url = f"https://www.spc.noaa.gov/products/{category}/{urlname}"
    name = Path(base).stem
    product = name
    return (name, url, product)

SPC_URLS = [_file_to_tuple(f) for f in SPC_FILES]


def ensure_spc_feature_tables() -> None:
    """Apply the single-feature SPC outlook schema (idempotent) and run DB init."""
    sql_file = ROOT / "db_init" / "03_spc_outlooks.sql"
    if sql_file.exists():
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(sql_file.read_text())
        except Exception:
            pass

    try:
        init_db()
    except Exception:
        pass


def save_example(name: str, url: str, content: bytes) -> None:
    fname = EXAMPLES_DIR / f"{name}.geojson"
    with open(fname, "wb") as f:
        f.write(content)


def upsert_convective(product: str, url: str, payload: dict) -> None:
    if not isinstance(payload, dict):
        return

    features = payload.get("features") or []
    issue_iso = payload.get("properties", {}).get("ISSUE_ISO") or payload.get("properties", {}).get("ISSUE") or ""

    insert_stmt = text(
        """
        INSERT INTO convective_outlooks (
            product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
            forecaster, label, label2, stroke, fill, geom, created_at
        ) VALUES (
            :product, :url, :payload, date_trunc('hour', now()), :feature_index, :properties, :dn,
            NULLIF(:valid_iso, '')::timestamptz, NULLIF(:expire_iso, '')::timestamptz, NULLIF(:issue_iso, '')::timestamptz,
            :forecaster, :label, :label2, :stroke, :fill,
            CASE WHEN :geom_json IS NULL THEN NULL ELSE ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON((:geom_json)::text)), 4326) END,
            now()
        )
        ON CONFLICT (product, issue, feature_index) DO UPDATE
            SET url = EXCLUDED.url,
                payload = EXCLUDED.payload,
                fetched_hour = EXCLUDED.fetched_hour,
                properties = EXCLUDED.properties,
                dn = EXCLUDED.dn,
                valid = EXCLUDED.valid,
                expire = EXCLUDED.expire,
                issue = EXCLUDED.issue,
                forecaster = EXCLUDED.forecaster,
                label = EXCLUDED.label,
                label2 = EXCLUDED.label2,
                stroke = EXCLUDED.stroke,
                fill = EXCLUDED.fill,
                geom = EXCLUDED.geom,
                created_at = EXCLUDED.created_at
        """
    ).bindparams(bindparam("geom_json", type_=sa.types.Text))

    with engine.begin() as conn:
        for idx, feat in enumerate(features):
            geom = feat.get("geometry")
            props = feat.get("properties") or {}
            dn_value = props.get("DN") if props.get("DN") is not None else "NA"
            params = {
                "product": product,
                "url": url,
                "payload": json.dumps(payload),
                "feature_index": idx,
                "properties": json.dumps(props),
                "dn": str(dn_value),
                "valid_iso": props.get("VALID_ISO") or props.get("VALID") or "",
                "expire_iso": props.get("EXPIRE_ISO") or props.get("EXPIRE") or "",
                "issue_iso": props.get("ISSUE_ISO") or props.get("ISSUE") or issue_iso,
                "forecaster": props.get("FORECASTER"),
                "label": props.get("LABEL"),
                "label2": props.get("LABEL2"),
                "stroke": props.get("stroke"),
                "fill": props.get("fill"),
                "geom_json": json.dumps(geom) if geom is not None else None,
            }

            try:
                # Write debug entry (best-effort)
                try:
                    for p in (Path(ROOT, "tmp", "spc_debug.log"), Path("/tmp", "spc_debug.log")):
                        try:
                            p.parent.mkdir(parents=True, exist_ok=True)
                        except Exception:
                            pass
                        try:
                            with open(p, "a") as df:
                                df.write(json.dumps({
                                    "type": "convective",
                                    "product": product,
                                    "url": url,
                                    "index": idx,
                                    "dn": params.get("dn"),
                                }) + "\n")
                        except Exception:
                            pass
                except Exception:
                    pass

                conn.execute(insert_stmt, params)
            except exc.DatabaseError as e:
                print(f"Warning: failed to upsert convective feature {idx} for {url}: {e}")


def upsert_fire(product: str, url: str, payload: dict) -> None:
    if not isinstance(payload, dict):
        return

    features = payload.get("features") or []
    issue_iso = payload.get("properties", {}).get("ISSUE_ISO") or payload.get("properties", {}).get("ISSUE") or ""

    insert_stmt = text(
        """
        INSERT INTO fire_outlooks (
            product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
            forecaster, label, label2, stroke, fill, geom, created_at
        ) VALUES (
            :product, :url, :payload, date_trunc('hour', now()), :feature_index, :properties, :dn,
            NULLIF(:valid_iso, '')::timestamptz, NULLIF(:expire_iso, '')::timestamptz, NULLIF(:issue_iso, '')::timestamptz,
            :forecaster, :label, :label2, :stroke, :fill,
            CASE WHEN :geom_json IS NULL THEN NULL ELSE ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON((:geom_json)::text)), 4326) END,
            now()
        )
        ON CONFLICT (product, issue, feature_index) DO UPDATE
            SET url = EXCLUDED.url,
                payload = EXCLUDED.payload,
                fetched_hour = EXCLUDED.fetched_hour,
                properties = EXCLUDED.properties,
                dn = EXCLUDED.dn,
                valid = EXCLUDED.valid,
                expire = EXCLUDED.expire,
                issue = EXCLUDED.issue,
                forecaster = EXCLUDED.forecaster,
                label = EXCLUDED.label,
                label2 = EXCLUDED.label2,
                stroke = EXCLUDED.stroke,
                fill = EXCLUDED.fill,
                geom = EXCLUDED.geom,
                created_at = EXCLUDED.created_at
        """
    ).bindparams(bindparam("geom_json", type_=sa.types.Text))

    with engine.begin() as conn:
        for idx, feat in enumerate(features):
            geom = feat.get("geometry")
            props = feat.get("properties") or {}
            params = {
                "product": product,
                "url": url,
                "payload": json.dumps(payload),
                "feature_index": idx,
                "properties": json.dumps(props),
                "dn": str(props.get("DN") if props.get("DN") is not None else "NA"),
                "valid_iso": props.get("VALID_ISO") or props.get("VALID") or "",
                "expire_iso": props.get("EXPIRE_ISO") or props.get("EXPIRE") or "",
                "issue_iso": props.get("ISSUE_ISO") or props.get("ISSUE") or issue_iso,
                "forecaster": props.get("FORECASTER"),
                "label": props.get("LABEL"),
                "label2": props.get("LABEL2"),
                "stroke": props.get("stroke"),
                "fill": props.get("fill"),
                "geom_json": json.dumps(geom) if geom is not None else None,
            }

            try:
                try:
                    for p in (Path(ROOT, "tmp", "spc_debug.log"), Path("/tmp", "spc_debug.log")):
                        try:
                            p.parent.mkdir(parents=True, exist_ok=True)
                        except Exception:
                            pass
                        try:
                            with open(p, "a") as df:
                                df.write(json.dumps({
                                    "type": "fire",
                                    "product": product,
                                    "url": url,
                                    "index": idx,
                                    "dn": params.get("dn"),
                                }) + "\n")
                        except Exception:
                            pass
                except Exception:
                    pass

                conn.execute(insert_stmt, params)
            except exc.DatabaseError as e:
                print(f"Warning: failed to upsert fire feature {idx} for {url}: {e}")


def fetch_and_store(name: str, url: str, product: str) -> None:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        content = r.content
        save_example(name, url, content)
        payload = r.json()
        if "/fire_wx/" in url or "fire_wx" in name:
            upsert_fire(product, url, payload)
        else:
            upsert_convective(product, url, payload)
        print(f"Stored {name} -> {url}")
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")


def fetch_all_once() -> None:
    for name, url, product in SPC_URLS:
        fetch_and_store(name, url, product)

    # After a full run, update ingest status
    try:
        with engine.begin() as conn:
            conv_count = conn.execute(text("SELECT count(*) FROM convective_outlooks")).scalar()
            fire_count = conn.execute(text("SELECT count(*) FROM fire_outlooks")).scalar()
            upsert = text(
                """
                INSERT INTO spc_ingest_status (source, last_run, last_success, convective_count, fire_count, updated_at)
                VALUES ('spc', date_trunc('second', now()), TRUE, :conv_count, :fire_count, now())
                ON CONFLICT (source) DO UPDATE SET
                  last_run = EXCLUDED.last_run,
                  last_success = EXCLUDED.last_success,
                  convective_count = EXCLUDED.convective_count,
                  fire_count = EXCLUDED.fire_count,
                  updated_at = EXCLUDED.updated_at;
                """
            )
            conn.execute(upsert, {"conv_count": conv_count, "fire_count": fire_count})
    except Exception:
        pass


def sleep_until_top_of_hour() -> None:
    now = datetime.utcnow()
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    delta = (next_hour - now).total_seconds()
    print(f"Sleeping {int(delta)}s until next top-of-hour: {next_hour.isoformat()} UTC")
    time.sleep(delta)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run continuously at top-of-hour")
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    args = parser.parse_args()

    try:
        load_dotenv()
    except Exception:
        pass

    env_once = os.getenv("SPC_ONCE", "").lower() in ("1", "true", "yes")
    env_auto = os.getenv("SPC_AUTO_REFRESH", "").lower()
    if env_auto == "":
        env_auto = True
    else:
        env_auto = env_auto in ("1", "true", "yes")

    interval_minutes = None
    if os.getenv("SPC_INTERVAL_MINUTES"):
        try:
            interval_minutes = int(os.getenv("SPC_INTERVAL_MINUTES"))
        except Exception:
            interval_minutes = None

    if args.once or env_once:
        ensure_spc_feature_tables()
        fetch_all_once()
        return

    should_loop = args.loop or env_auto
    if should_loop:
        print("SPC poller: running in loop mode")
        ensure_spc_feature_tables()
        fetch_all_once()
        while True:
            if interval_minutes and interval_minutes > 0:
                print(f"Sleeping {interval_minutes} minutes between fetches")
                time.sleep(interval_minutes * 60)
                fetch_all_once()
            else:
                sleep_until_top_of_hour()
                fetch_all_once()


if __name__ == "__main__":
    main()
