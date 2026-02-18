# Weather Alert Router 🚨

Weather-Alert-Router ingests, stores and serves US National Weather Service (NWS) alerts. It runs as a small Docker Compose stack (FastAPI + PostGIS) so you can run it on a home PC or server.

Quick links
- Install & run: [README_INSTALL.md](README_INSTALL.md) 📦

What it does
- Ingests NWS `/alerts` into a PostGIS-enabled PostgreSQL database
- Public read-only API for alerts (GET /alerts)
- Authenticated POST endpoint for accepted alert submissions (X-API-Key)
- Admin UI for managing API keys (bound to localhost by default)

Quick start (short)
1. Follow the install steps in [README_INSTALL.md](README_INSTALL.md).
2. Copy `.env.example` to `.env` and edit values if needed.
3. Start the stack:

```bash
docker compose up --build
```

4. Open the API: `http://localhost:31800/alerts` (or see `.env` / `docker-compose.yml` for ports) 🌐

Notes
- Seeds: initial DB seeds (alert types and keywords) live in `db_init/` and run automatically when a fresh Postgres data directory is created. They are idempotent so running them again won't overwrite custom values.
- Preserve data: do NOT run `docker compose down -v` unless you want to wipe the database (this deletes stored alerts).
- If you want help, open an issue or ask for a walkthrough. 🙂

Important — Disclaimer
- Please review the project disclaimer before using or deploying: [DISCLAIMER.md](DISCLAIMER.md) ⚠️
