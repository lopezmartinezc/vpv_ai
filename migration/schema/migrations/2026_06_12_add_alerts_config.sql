-- Per-season opt-in/out toggles for which events emit Telegram alerts.
-- JSONB shape (all keys optional, missing ⇒ enabled):
--   { "events": { "deadline_reminder": true,
--                 "lineup_submitted": false,
--                 "live_match_events": true } }
-- Idempotent: safe to re-run.
ALTER TABLE seasons ADD COLUMN IF NOT EXISTS alerts_config JSONB;
