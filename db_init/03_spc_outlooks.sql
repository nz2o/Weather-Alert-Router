-- Single feature-level tables for SPC convective and fire outlooks
-- Each row represents a single GeoJSON Feature tied to a product+issue
CREATE TABLE IF NOT EXISTS convective_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
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
  UNIQUE(product, issue, feature_index)
);
CREATE INDEX IF NOT EXISTS idx_convective_outlooks_geom ON convective_outlooks USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_convective_outlooks_product_issue ON convective_outlooks (product, issue);

CREATE TABLE IF NOT EXISTS fire_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
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
  UNIQUE(product, issue, feature_index)
);
CREATE INDEX IF NOT EXISTS idx_fire_outlooks_geom ON fire_outlooks USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_fire_outlooks_product_issue ON fire_outlooks (product, issue);

-- End of spc outlooks schema
