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
                    # If running against an older DB with separate *_features tables,
                    # perform a migration into the new single-table schema.
                    # Detect old feature tables
                    has_conv_features = conn.execute(text("SELECT to_regclass('public.convective_features')")).scalar()
                    has_fire_features = conn.execute(text("SELECT to_regclass('public.fire_features')")).scalar()

                    # First, create the new single-table schema in a safe way
                    conn.exec_driver_sql(sql_text)

                    # If old feature tables exist, migrate their rows into the new single table
                    if has_conv_features:
                        # Create a temp new table (if not exists) and populate from old tables
                        conn.exec_driver_sql(
                            """
                            CREATE TABLE IF NOT EXISTS convective_outlooks_new AS
                              SELECT NULL::serial AS id LIMIT 0;
                            """
                        )
                        # Create the proper schema for convective_outlooks_new
                        conn.exec_driver_sql(sql_text.replace('CREATE TABLE IF NOT EXISTS convective_outlooks', 'CREATE TABLE IF NOT EXISTS convective_outlooks_new'))
                        conn.exec_driver_sql(
                            """
                            INSERT INTO convective_outlooks_new (
                              product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
                              forecaster, label, label2, stroke, fill, geom, created_at
                            )
                            SELECT o.product, o.url, o.payload, o.fetched_hour, f.feature_index, f.properties, f.dn, f.valid, f.expire,
                                   COALESCE(f.issue, o.issue), f.forecaster, f.label, f.label2, f.stroke, f.fill, f.geom, f.created_at
                            FROM convective_outlooks o JOIN convective_features f ON f.outlook_id = o.id
                            ON CONFLICT DO NOTHING;
                            """
                        )
                        # Preserve old tables by renaming and swap in new table
                        conn.exec_driver_sql("ALTER TABLE convective_outlooks RENAME TO convective_outlooks_old;")
                        conn.exec_driver_sql("ALTER TABLE convective_features RENAME TO convective_features_old;")
                        conn.exec_driver_sql("ALTER TABLE convective_outlooks_new RENAME TO convective_outlooks;")

                    if has_fire_features:
                        conn.exec_driver_sql(sql_text.replace('convective_outlooks', 'fire_outlooks').replace('CREATE TABLE IF NOT EXISTS fire_outlooks', 'CREATE TABLE IF NOT EXISTS fire_outlooks_new'))
                        conn.exec_driver_sql(
                            """
                            INSERT INTO fire_outlooks_new (
                              product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
                              forecaster, label, label2, stroke, fill, geom, created_at
                            )
                            SELECT o.product, o.url, o.payload, o.fetched_hour, f.feature_index, f.properties, f.dn, f.valid, f.expire,
                                   COALESCE(f.issue, o.issue), f.forecaster, f.label, f.label2, f.stroke, f.fill, f.geom, f.created_at
                            FROM fire_outlooks o JOIN fire_features f ON f.outlook_id = o.id
                            ON CONFLICT DO NOTHING;
                            """
                        )
                        conn.exec_driver_sql("ALTER TABLE fire_outlooks RENAME TO fire_outlooks_old;")
                        conn.exec_driver_sql("ALTER TABLE fire_features RENAME TO fire_features_old;")
                        conn.exec_driver_sql("ALTER TABLE fire_outlooks_new RENAME TO fire_outlooks;")
                    
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
