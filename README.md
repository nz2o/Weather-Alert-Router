# Weather Alert Router

Experimental project to ingest, store and serve weather alerts from the US NWS `/alerts` API.

Features
- Ingest alerts into PostGIS-enabled PostgreSQL
- Public read-only API for alerts
- Authenticated POST endpoint for accepted alert submissions (API-key protected)
- Runs in Docker via `docker-compose`

Quick start

1. Copy `.env.example` to `.env` and edit DB credentials if needed.
2. Build and start services:

```bash
docker-compose up --build
```

3. API will be available at `http://localhost:8000`.

Notes
- This is experimental/non-operational — see `DISCLAIMER.md`.
 
Deployment notes
- **Python runtime:** services run on Python 3.13.
- **Database:** the stack uses PostGIS (image: `postgis/postgis:18-3.6`) — ensure the database supports PostGIS extensions.
- **Environment variables:**
	- `LOAD_EXAMPLE_JSON` — when set to `true` the ingest service will load `examples/alerts_snapshot.json` on startup to seed the DB for testing.
	- `WAIT_FOR_APP` — when set to `true` the ingest service will wait for the `app` HTTP endpoint to report healthy before running (useful for reliable startup ordering).
	- `WAIT_FOR_APP_TIMEOUT` — timeout in seconds for the wait loop.
- **Schema changes and DB wipe:** If you change ORM models or column types you may encounter missing-column errors. In that case recreate the DB volume to allow a fresh schema:

```bash
docker-compose down -v
docker-compose up --build
```

This will remove the Postgres volume and recreate the DB with the updated schema. Use with caution — you will lose stored alerts.
# Weather-Alert-Router
An API and solution to route NWS alerts and storm reports
