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
# Weather-Alert-Router
An API and solution to route NWS alerts and storm reports
