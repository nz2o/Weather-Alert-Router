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

Docker networks and Traefik
--------------------------

This compose file configures an internal `internal` bridge network for service-to-service communication and references an external `traefik-public` network so you can attach Traefik in your home lab. `traefik-public` is declared as an external network in `docker-compose.yml` so Traefik (managed outside this compose) can route to the `app` service.

If you use Traefik, create or ensure the network exists:

```bash
docker network create traefik-public
```

The `app` service is connected to both `internal` and `traefik-public` so you can either access it directly via the exposed host port (`31800`) or let Traefik route traffic to the internal container port `8000`. Example Traefik labels (already shown as comments in `docker-compose.yml`) can be adapted for your Traefik setup.

Notes
- `app` host port: `31800` -> container `8000`
- `admin_ui` host binding: `127.0.0.1:31802` -> container `8080` (bound to localhost for safety)

Health-aware startup (optional)
--------------------------------

If you want Docker Compose to wait for services to become healthy before starting dependents, use the provided override file which enables `depends_on.condition: service_healthy` behavior (Compose v2.4 format):

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

This will respect the `healthcheck` definitions in `docker-compose.yml` so `app`, `ingest`, and `admin_ui` will wait until `db` (and `app` where appropriate) report healthy.



If you want to expose it differently, edit `docker-compose.yml` to change the `ports` mapping (or remove `127.0.0.1:` to make it public). Use firewall rules to restrict access to the chosen port.
```


