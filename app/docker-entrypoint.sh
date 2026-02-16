#!/bin/sh
set -e

python - <<'PY'
import os, time, sys
import psycopg2

host=os.getenv('POSTGRES_HOST','db')
port=int(os.getenv('POSTGRES_PORT','5432'))
user=os.getenv('POSTGRES_USER','alerts')
password=os.getenv('POSTGRES_PASSWORD','alerts')
db=os.getenv('POSTGRES_DB','alerts')
timeout=int(os.getenv('DB_WAIT_TIMEOUT','60'))
start=time.time()
while True:
    try:
        conn=psycopg2.connect(host=host,port=port,user=user,password=password,database=db,connect_timeout=5)
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
