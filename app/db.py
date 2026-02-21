from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv('POSTGRES_USER', 'alerts')
DB_PASS = os.getenv('POSTGRES_PASSWORD', 'alerts')
DB_HOST = os.getenv('POSTGRES_HOST', 'db')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'alerts')

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def init_db():
    """Create tables and ensure PostGIS spatial index exists.

    - Runs SQL to create the `postgis` extension if available (best-effort).
    - Creates a GiST index on `alerts.geometry` if it doesn't already exist.
    """
    Base.metadata.create_all(bind=engine)

    # Ensure PostGIS extension and spatial index (best-effort; ignore failures)
    try:
        with engine.connect() as conn:
            # Create extension if possible (may require superuser; ignore errors)
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            except Exception:
                pass

            # Create a GiST spatial index on alerts.geometry if it doesn't exist
            try:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_geometry ON alerts USING GIST (geometry);"
                ))
            except Exception:
                pass
            conn.commit()
    except Exception:
        # If engine connection itself fails (DB not ready), let the caller retry via container restart
        pass

    # Ensure extracted columns exist (best-effort ALTER TABLE statements)
    try:
        with engine.connect() as conn:
            alter_stmts = [
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS sent timestamptz",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS effective timestamptz",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS onset timestamptz",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS expires timestamptz",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS ends timestamptz",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS status varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS message_type varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS category varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS severity varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS certainty varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS urgency varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS event varchar(512)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS sender varchar(256)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS sender_name varchar(256)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS headline varchar(512)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS area_desc varchar(1024)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS description text",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS instruction text",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS response varchar(128)",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS geocode jsonb",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS parameters jsonb",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS affected_zones jsonb",
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS references jsonb",
            ]
            for s in alter_stmts:
                try:
                    conn.execute(text(s))
                except Exception:
                    pass
            # Add an index on sent for faster time-range queries
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts (sent);"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass

    # Ensure SPC outlooks have `issue` column and unique index on (product, issue)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE convective_outlooks ADD COLUMN IF NOT EXISTS issue timestamptz;"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE fire_outlooks ADD COLUMN IF NOT EXISTS issue timestamptz;"))
            except Exception:
                pass
            try:
                # Create a unique index on product + issue to support upserts by product+issue
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_convective_product_issue ON convective_outlooks (product, issue);"))
            except Exception:
                pass
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_fire_product_issue ON fire_outlooks (product, issue);"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass

    # If there's a SQL migration file for SPC outlooks (db_init/03_spc_outlooks.sql), apply it idempotently.
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        sql_file = root / 'db_init' / '03_spc_outlooks.sql'
        if sql_file.exists():
            with engine.begin() as conn:
                try:
                    sql_text = sql_file.read_text()
                    # exec_driver_sql runs the raw SQL (supports multiple statements)
                    conn.exec_driver_sql(sql_text)
                except Exception:
                    # If the DB user cannot create extensions or types, ignore and continue
                    pass
    except Exception:
        pass

    # Drop the `sender` column if present (we no longer persist it separately)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE alerts DROP COLUMN IF EXISTS sender;"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass
