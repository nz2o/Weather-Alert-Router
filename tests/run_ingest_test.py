"""Integration test: run fetch_and_store once against configured DB.

Run inside the app container after `docker-compose up`:

    python tests/run_ingest_test.py

This will call `app.ingest.fetch_and_store(limit=5)` and exit with code 0 on success.
"""
import sys
from app.ingest import fetch_and_store


def main():
    try:
        fetch_and_store(limit=5)
        print("fetch_and_store completed")
        return 0
    except Exception as e:
        print("fetch_and_store failed:", e)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
