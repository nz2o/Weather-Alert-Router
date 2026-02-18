# Installation

1. Copy `.env.example` to `.env` and edit if needed.

```bash
cp .env.example .env
```

2. Start services

```bash
docker-compose up --build
```

Environment variables
---------------------

- `LOAD_EXAMPLE_JSON`: set to `true` to load `examples/alerts_snapshot.json` into the database on ingest startup (useful for development/testing).
- `WAIT_FOR_APP`: set to `true` to make the ingest service wait until the `app` HTTP endpoint is healthy before ingesting.
- `WAIT_FOR_APP_TIMEOUT`: number of seconds the ingest wait loop will poll for app readiness before giving up.

Wiping the DB for schema changes
--------------------------------

If you change database models or column types and see errors about missing columns, recreate the Postgres volume and restart the stack to provision a clean schema:

```bash
docker-compose down -v
docker-compose up --build
```

This will delete the database volume and all stored alerts — only use when you intentionally want a clean database.

Seeding example data
--------------------

To seed example data via the ingest service, either set `LOAD_EXAMPLE_JSON=true` in your `.env` and restart the ingest container, or run the ingest module directly with the environment variable for a one-off load:

```bash
LOAD_EXAMPLE_JSON=true docker-compose run --rm ingest
```

3. To ingest alerts manually:

```bash
docker-compose exec app python -m app.ingest
```

4. To run the ingest service continuously (separate container):

```bash
docker-compose up --build ingest
```

5. To run the simple integration test (requires DB up):

```bash
docker-compose up -d db
docker-compose build app
docker-compose run --rm --service-ports app python tests/run_ingest_test.py
```

Admin UI
---------

The admin UI for API key management is protected by an `ADMIN_KEY` value. Set `ADMIN_KEY` in your `.env` (see `.env.example`). When calling the admin UI from a browser, include the header `X-Admin-Key: <ADMIN_KEY>` in the request. For curl examples:

```bash
# List keys (header required)
curl -H "X-Admin-Key: $ADMIN_KEY" http://localhost:8000/admin/apikeys

# Create a key (form)
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" -d "owner=me" http://localhost:8000/admin/apikeys/create

Client-side admin UI (separate port)
-----------------------------------

An admin client UI is available as a lightweight single-page app served from a separate container bound to `127.0.0.1:31802` by default. The admin client proxies admin operations through the server, so the `ADMIN_KEY` never reaches the browser. The server issues short-lived CSRF tokens to the page which must be presented on mutating requests. It's intentionally bound to localhost; you can instead bind it to another interface or protect it with firewall rules.

Start it with:

```bash
docker-compose up --build admin_ui
```

Open in a browser on the host:

```
http://127.0.0.1:31802/
```
# Installation — non-technical guide 🧭

This guide walks a non-technical user through running Weather-Alert-Router on a home computer using Docker. If you do not yet have Docker installed, see the official instructions: https://docs.docker.com/get-docker/ 📚

Prerequisites
- A computer with Docker (or Docker Desktop) installed: https://docs.docker.com/get-docker/ ✅
- Docker Compose (typically comes with Docker Desktop). If needed, see: https://docs.docker.com/compose/install/ 🧩
- A basic terminal / command prompt and editor to copy the example `.env` file.

Optional helper UIs
- If you prefer a browser-based Docker management UI on Linux, consider Portainer (Community Edition): https://www.portainer.io/ or an alternative such as Arcane. These provide an easy GUI for starting/stopping containers and viewing logs for less-technical users. 🧰
- On Windows, Docker Desktop includes a GUI and integrates Compose — recommended for most users: https://www.docker.com/products/docker-desktop 🪟

Important — Disclaimer
- Please read the project disclaimer before running this software: [DISCLAIMER.md](DISCLAIMER.md) ⚠️

Quick start (simple, 5 steps)
1. Open a terminal/command prompt and go to the project folder.
2. Copy the example environment file:

```bash
cp .env.example .env
# Edit .env with a text editor if you need to change defaults (optional)
```

3. Start the services:

```bash
docker compose up --build
```

4. Wait a minute for services to start. Open your browser and visit:
- API: http://localhost:31800/alerts 🌐
- Admin UI (local only): http://127.0.0.1:31802/ 🔒

5. Stop the stack when you are done:

```bash
docker compose down
```

How the database is seeded (no extra steps)
- On first run the Postgres container will run any scripts in `db_init/`. This project seeds `alert_types` and `alert_keywords` automatically so you don't need to refresh them repeatedly. The seed scripts are idempotent and will not overwrite custom values.
- Important: do NOT run `docker compose down -v` unless you want to wipe the database and start fresh — that deletes all stored alerts and data.

Environment variables (easy language)
- `LOAD_EXAMPLE_JSON` — set to `true` if you want a small example dataset loaded for testing.
- `WAIT_FOR_APP` — set to `true` so the ingest service waits for the API to be ready before starting to ingest (recommended).

Common commands (copy/paste)
- Start in background: `docker compose up -d --build`
- See logs: `docker compose logs -f --tail=200 app db ingest admin_ui`
- Run one-off seed or ingest: `docker compose exec app python -m app.ingest`

Troubleshooting tips (non-technical)
- If ports conflict: change the ports in `docker-compose.yml` (look for `31800` and `31802`) or stop other services using those ports.
- If the database reports missing columns after a code change, you can recreate a fresh database (this deletes all data):

```bash
docker compose down -v
docker compose up --build
```

Need help?
- If you'd like, I can add a button or a small script to simplify starting/stopping the stack for non-technical users. Tell me if you want that. 👍


