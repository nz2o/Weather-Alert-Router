-- Create tables for SPC convective outlooks and fire weather outlooks

CREATE TABLE IF NOT EXISTS convective_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(url, fetched_hour)
);

CREATE INDEX IF NOT EXISTS idx_convective_outlooks_product ON convective_outlooks(product);
CREATE INDEX IF NOT EXISTS idx_convective_outlooks_fetched_hour ON convective_outlooks(fetched_hour);

CREATE TABLE IF NOT EXISTS fire_outlooks (
  id serial PRIMARY KEY,
  product text NOT NULL,
  url text NOT NULL,
  payload jsonb,
  fetched_hour timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(url, fetched_hour)
);

CREATE INDEX IF NOT EXISTS idx_fire_outlooks_product ON fire_outlooks(product);
CREATE INDEX IF NOT EXISTS idx_fire_outlooks_fetched_hour ON fire_outlooks(fetched_hour);

-- End of spc outlooks schema
