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

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
