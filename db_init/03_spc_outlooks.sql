-- Create tables for SPC convective outlooks and fire weather outlooks

CREATE TABLE IF NOT EXISTS convective_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  -- The `issue` timestamp is used as a canonical identifier from the payload's ISSUE/ISSUE_ISO
  issue timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(product, issue)
);

CREATE INDEX IF NOT EXISTS idx_convective_outlooks_product ON convective_outlooks(product);
CREATE INDEX IF NOT EXISTS idx_convective_outlooks_fetched_hour ON convective_outlooks(fetched_hour);

CREATE TABLE IF NOT EXISTS fire_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  issue timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(product, issue)
);

CREATE INDEX IF NOT EXISTS idx_fire_outlooks_product ON fire_outlooks(product);
CREATE INDEX IF NOT EXISTS idx_fire_outlooks_fetched_hour ON fire_outlooks(fetched_hour);

-- End of spc outlooks schema
-- Feature-level tables: each GeoJSON Feature becomes a row with parsed properties and a PostGIS geometry
CREATE TABLE IF NOT EXISTS convective_features (
  id serial PRIMARY KEY,
  outlook_id integer NOT NULL REFERENCES convective_outlooks(id) ON DELETE CASCADE,
  feature_index integer NOT NULL,
  properties jsonb,
  dn integer,
  valid timestamptz,
  expire timestamptz,
  issue timestamptz,
  forecaster text,
  label text,
  label2 text,
  stroke text,
  fill text,
  geom geometry(Geometry,4326),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(outlook_id, feature_index)
);
CREATE INDEX IF NOT EXISTS idx_convective_features_geom ON convective_features USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_convective_features_dn ON convective_features (dn);

CREATE TABLE IF NOT EXISTS fire_features (
  id serial PRIMARY KEY,
  outlook_id integer NOT NULL REFERENCES fire_outlooks(id) ON DELETE CASCADE,
  feature_index integer NOT NULL,
  properties jsonb,
  dn integer,
  valid timestamptz,
  expire timestamptz,
  issue timestamptz,
  forecaster text,
  label text,
  label2 text,
  stroke text,
  fill text,
  geom geometry(Geometry,4326),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(outlook_id, feature_index)
);
CREATE INDEX IF NOT EXISTS idx_fire_features_geom ON fire_features USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_fire_features_dn ON fire_features (dn);
