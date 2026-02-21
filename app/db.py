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
                # Drop any legacy unique indexes that included dn to allow schema migration
                try:
                    conn.execute(text("DROP INDEX IF EXISTS uq_convective_product_issue_dn;"))
                except Exception:
                    pass
                try:
                    conn.execute(text("DROP INDEX IF EXISTS uq_fire_product_issue_dn;"))
                except Exception:
                    pass
                # Create a unique index on product + issue + feature_index to support idempotent upserts
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_convective_product_issue_featidx ON convective_outlooks (product, issue, feature_index);"))
            except Exception:
                pass
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_fire_product_issue_featidx ON fire_outlooks (product, issue, feature_index);"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass

    # Ensure dn column is text for both outlook tables (convert existing integer values to text)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE convective_outlooks ALTER COLUMN dn TYPE text USING dn::text;"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE fire_outlooks ALTER COLUMN dn TYPE text USING dn::text;"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass

    # If there's a SQL migration file for SPC outlooks (db_init/03_spc_outlooks.sql), apply it idempotently
    # and migrate any legacy *_features rows into the single-feature outlook tables.
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        sql_file = root / 'db_init' / '03_spc_outlooks.sql'
        if sql_file.exists():
            with engine.begin() as conn:
                try:
                    sql_text = sql_file.read_text()
                    # Ensure the new single-table schema exists (idempotent)
                    conn.exec_driver_sql(sql_text)

                    # Detect legacy feature tables
                    has_conv_features = conn.execute(text("SELECT to_regclass('public.convective_features')")).scalar()
                    has_fire_features = conn.execute(text("SELECT to_regclass('public.fire_features')")).scalar()

                    # Migrate convective features into convective_outlooks if present
                    if has_conv_features:
                        try:
                            conn.exec_driver_sql(
                                """
                                INSERT INTO convective_outlooks (
                                  product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
                                  forecaster, label, label2, stroke, fill, geom, created_at
                                )
                                SELECT o.product, o.url, o.payload, COALESCE(o.fetched_hour, now()), f.feature_index, f.properties, f.dn, f.valid, f.expire,
                                       COALESCE(f.issue, o.issue), f.forecaster, f.label, f.label2, f.stroke, f.fill, f.geom, f.created_at
                                    FROM convective_outlooks o JOIN convective_features f ON f.outlook_id = o.id
                                                                    ON CONFLICT (product, issue) DO UPDATE
                                  SET payload = EXCLUDED.payload,
                                      properties = EXCLUDED.properties,
                                      dn = EXCLUDED.dn,
                                      valid = EXCLUDED.valid,
                                      expire = EXCLUDED.expire,
                                      forecaster = EXCLUDED.forecaster,
                                      label = EXCLUDED.label,
                                      label2 = EXCLUDED.label2,
                                      stroke = EXCLUDED.stroke,
                                      fill = EXCLUDED.fill,
                                      geom = EXCLUDED.geom,
                                      created_at = EXCLUDED.created_at;
                                """
                            )
                            # Rename the old feature table to preserve data (non-destructive)
                            conn.exec_driver_sql("ALTER TABLE IF EXISTS convective_features RENAME TO convective_features_old;")
                        except Exception:
                            # If migration fails for any reason, don't block startup
                            pass

                    # Normalize geometry to Multi* for compatibility (safe if already multi)
                    try:
                        conn.exec_driver_sql("UPDATE convective_outlooks SET geom = ST_Multi(geom) WHERE geom IS NOT NULL;")
                        conn.exec_driver_sql("UPDATE fire_outlooks SET geom = ST_Multi(geom) WHERE geom IS NOT NULL;")
                    except Exception:
                        pass

                    # Migrate fire features into fire_outlooks if present
                    if has_fire_features:
                        try:
                            conn.exec_driver_sql(
                                """
                                INSERT INTO fire_outlooks (
                                  product, url, payload, fetched_hour, feature_index, properties, dn, valid, expire, issue,
                                  forecaster, label, label2, stroke, fill, geom, created_at
                                )
                                SELECT o.product, o.url, o.payload, COALESCE(o.fetched_hour, now()), f.feature_index, f.properties, f.dn, f.valid, f.expire,
                                       COALESCE(f.issue, o.issue), f.forecaster, f.label, f.label2, f.stroke, f.fill, f.geom, f.created_at
                                FROM fire_outlooks o JOIN fire_features f ON f.outlook_id = o.id
                                ON CONFLICT (product, issue) DO UPDATE
                                  SET payload = EXCLUDED.payload,
                                      properties = EXCLUDED.properties,
                                      dn = EXCLUDED.dn,
                                      valid = EXCLUDED.valid,
                                      expire = EXCLUDED.expire,
                                      forecaster = EXCLUDED.forecaster,
                                      label = EXCLUDED.label,
                                      label2 = EXCLUDED.label2,
                                      stroke = EXCLUDED.stroke,
                                      fill = EXCLUDED.fill,
                                      geom = EXCLUDED.geom,
                                      created_at = EXCLUDED.created_at;
                                """
                            )
                            conn.exec_driver_sql("ALTER TABLE IF EXISTS fire_features RENAME TO fire_features_old;")
                        except Exception:
                            pass

                    # If some rows were created with only `payload` populated (legacy/migration issues),
                    # extract the first feature's properties/geometry into typed columns.
                    try:
                        conn.exec_driver_sql(
                            """
                            -- Populate convective_outlooks typed columns from payload->features[0]
                            UPDATE convective_outlooks SET
                                properties = payload->'features'->0->'properties',
                                dn = COALESCE(NULLIF((payload->'features'->0->'properties'->>'DN'),'') , 'NA'),
                                valid = NULLIF(payload->'features'->0->'properties'->>'VALID_ISO','')::timestamptz,
                                expire = NULLIF(payload->'features'->0->'properties'->>'EXPIRE_ISO','')::timestamptz,
                                issue = NULLIF(payload->'features'->0->'properties'->>'ISSUE_ISO','')::timestamptz,
                                forecaster = payload->'features'->0->'properties'->>'FORECASTER',
                                label = payload->'features'->0->'properties'->>'LABEL',
                                label2 = payload->'features'->0->'properties'->>'LABEL2',
                                stroke = payload->'features'->0->'properties'->>'stroke',
                                fill = payload->'features'->0->'properties'->>'fill',
                                geom = CASE WHEN (payload->'features'->0->'geometry') IS NULL OR (payload->'features'->0->'geometry') = 'null' THEN geom ELSE ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON((payload->'features'->0->'geometry')::text)),4326) END
                            WHERE (payload->'features'->0->'properties') IS NOT NULL;

                            -- Populate fire_outlooks typed columns from payload->features[0]
                            UPDATE fire_outlooks SET
                                properties = payload->'features'->0->'properties',
                                dn = COALESCE(NULLIF((payload->'features'->0->'properties'->>'DN'),'') , 'NA'),
                                valid = NULLIF(payload->'features'->0->'properties'->>'VALID_ISO','')::timestamptz,
                                expire = NULLIF(payload->'features'->0->'properties'->>'EXPIRE_ISO','')::timestamptz,
                                issue = NULLIF(payload->'features'->0->'properties'->>'ISSUE_ISO','')::timestamptz,
                                forecaster = payload->'features'->0->'properties'->>'FORECASTER',
                                label = payload->'features'->0->'properties'->>'LABEL',
                                label2 = payload->'features'->0->'properties'->>'LABEL2',
                                stroke = payload->'features'->0->'properties'->>'stroke',
                                fill = payload->'features'->0->'properties'->>'fill',
                                geom = CASE WHEN (payload->'features'->0->'geometry') IS NULL OR (payload->'features'->0->'geometry') = 'null' THEN geom ELSE ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON((payload->'features'->0->'geometry')::text)),4326) END
                            WHERE (payload->'features'->0->'properties') IS NOT NULL;
                            """
                        )
                    except Exception:
                        pass

                    # Ensure DN matches the stored properties (do NOT append suffixes)
                    try:
                        conn.exec_driver_sql(
                            """
                            UPDATE convective_outlooks SET dn = COALESCE(NULLIF(properties->>'DN',''), COALESCE(NULLIF((payload->'features'->0->'properties'->>'DN'),''),'NA'));
                            UPDATE fire_outlooks SET dn = COALESCE(NULLIF(properties->>'DN',''), COALESCE(NULLIF((payload->'features'->0->'properties'->>'DN'),''),'NA'));
                            -- Recompute feature_index by finding the ordinal of the matching properties JSON in the payload features
                            UPDATE convective_outlooks c SET feature_index = sub.idx
                            FROM (
                                SELECT c2.id,
                                    (SELECT (fe.ord - 1)
                                     FROM jsonb_array_elements(c2.payload->'features') WITH ORDINALITY AS fe(elem, ord)
                                     WHERE fe.elem->'properties' = c2.properties
                                     LIMIT 1) AS idx
                                FROM convective_outlooks c2
                                WHERE c2.feature_index IS NULL OR c2.feature_index = 0
                            ) sub
                            WHERE c.id = sub.id AND sub.idx IS NOT NULL;

                            UPDATE fire_outlooks c SET feature_index = sub.idx
                            FROM (
                                SELECT c2.id,
                                    (SELECT (fe.ord - 1)
                                     FROM jsonb_array_elements(c2.payload->'features') WITH ORDINALITY AS fe(elem, ord)
                                     WHERE fe.elem->'properties' = c2.properties
                                     LIMIT 1) AS idx
                                FROM fire_outlooks c2
                                WHERE c2.feature_index IS NULL OR c2.feature_index = 0
                            ) sub
                            WHERE c.id = sub.id AND sub.idx IS NOT NULL;

                            -- fallback: ensure no NULLs remain
                            UPDATE convective_outlooks SET feature_index = 0 WHERE feature_index IS NULL;
                            UPDATE fire_outlooks SET feature_index = 0 WHERE feature_index IS NULL;
                            """
                        )
                    except Exception:
                        pass

                    # Additional fixes: clean DN suffixes (eg. '-<id>') introduced earlier,
                    # and recompute feature_index by matching properties/DN to payload features.
                    try:
                        conn.exec_driver_sql(
                            """
                            -- Remove appended -<id> suffixes from dn if present
                            UPDATE convective_outlooks SET dn = regexp_replace(dn, '-[0-9]+$','') WHERE dn ~ '-[0-9]+$';
                            UPDATE fire_outlooks SET dn = regexp_replace(dn, '-[0-9]+$','') WHERE dn ~ '-[0-9]+$';

                            -- Recompute feature_index by matching properties JSON or DN within the payload features
                            UPDATE convective_outlooks c SET feature_index = sub.idx
                            FROM (
                                SELECT c2.id,
                                    (SELECT (fe.ord - 1)
                                     FROM jsonb_array_elements(c2.payload->'features') WITH ORDINALITY AS fe(elem, ord)
                                     WHERE (fe.elem->'properties') IS NOT NULL
                                         AND ((fe.elem->'properties') = c2.properties OR (fe.elem->'properties'->>'DN') = c2.properties->>'DN')
                                     LIMIT 1) AS idx
                                FROM convective_outlooks c2
                                WHERE c2.feature_index IS NULL
                            ) sub
                            WHERE c.id = sub.id AND sub.idx IS NOT NULL;

                            UPDATE fire_outlooks c SET feature_index = sub.idx
                            FROM (
                                SELECT c2.id,
                                    (SELECT (fe.ord - 1)
                                     FROM jsonb_array_elements(c2.payload->'features') WITH ORDINALITY AS fe(elem, ord)
                                     WHERE (fe.elem->'properties') IS NOT NULL
                                         AND ((fe.elem->'properties') = c2.properties OR (fe.elem->'properties'->>'DN') = c2.properties->>'DN')
                                     LIMIT 1) AS idx
                                FROM fire_outlooks c2
                                WHERE c2.feature_index IS NULL
                            ) sub
                            WHERE c.id = sub.id AND sub.idx IS NOT NULL;

                            -- fallback: set any remaining NULL indices to 0
                            UPDATE convective_outlooks SET feature_index = 0 WHERE feature_index IS NULL;
                            UPDATE fire_outlooks SET feature_index = 0 WHERE feature_index IS NULL;
                            """
                        )
                    except Exception:
                        pass
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
