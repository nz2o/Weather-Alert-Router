-- Idempotent creation and seeding of alert_keywords
CREATE TABLE IF NOT EXISTS alert_keywords (
  keyword text PRIMARY KEY,
  emoji text,
  color text, -- hex RGB (#rrggbb)
  payload jsonb,
  created_at timestamptz DEFAULT now()
);

-- Insert or update but do not overwrite existing non-null emoji/color/payload
INSERT INTO alert_keywords (keyword, emoji, color, payload) VALUES
('Outage', '📴', '#6c757d', jsonb_build_object('name','Outage')),
('Message', '📢', '#007bff', jsonb_build_object('name','Message')),
('Alert', '⚠️', '#ffc107', jsonb_build_object('name','Alert')),
('Advisory', 'ℹ️', '#17a2b8', jsonb_build_object('name','Advisory')),
('Warning', '🚨', '#dc3545', jsonb_build_object('name','Warning')),
('Watch', '👀', '#fd7e14', jsonb_build_object('name','Watch')),
('Statement', '📝', '#6f42c1', jsonb_build_object('name','Statement')),
('Emergency', '🚨', '#b21f2d', jsonb_build_object('name','Emergency')),
('Immediate', '⏱️', '#c82333', jsonb_build_object('name','Immediate')),
('Danger', '☠️', '#800000', jsonb_build_object('name','Danger')),
('Test', '🔁', '#0d6efd', jsonb_build_object('name','Test'))
ON CONFLICT (keyword) DO UPDATE
  SET emoji = COALESCE(alert_keywords.emoji, EXCLUDED.emoji),
      color = COALESCE(alert_keywords.color, EXCLUDED.color),
      payload = COALESCE(alert_keywords.payload, EXCLUDED.payload);

-- end
