#!/bin/sh
set -e

python - <<'PY'
import os, time, sys
try:
    import psycopg
except Exception:
    # Fallback to psycopg2 for compatibility
    import psycopg2 as psycopg

host=os.getenv('POSTGRES_HOST','db')
port=int(os.getenv('POSTGRES_PORT','5432'))
user=os.getenv('POSTGRES_USER','alerts')
password=os.getenv('POSTGRES_PASSWORD','alerts')
db=os.getenv('POSTGRES_DB','alerts')
timeout=int(os.getenv('DB_WAIT_TIMEOUT','60'))
start=time.time()
while True:
    try:
        # psycopg (v3) uses psycopg.connect, psycopg2 compatibility is maintained via alias
        conn = psycopg.connect(host=host, port=port, user=user, password=password, dbname=db, connect_timeout=5)
        conn.close()
        print('Database reachable')
        break
    except Exception as e:
        if time.time()-start>timeout:
            print('Timed out waiting for database', file=sys.stderr)
            sys.exit(1)
        print('Waiting for database...', flush=True)
        time.sleep(2)
PY

exec "$@"
