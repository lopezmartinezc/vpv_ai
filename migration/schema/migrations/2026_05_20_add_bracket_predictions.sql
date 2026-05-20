-- Migration: add bracket_predictions JSONB to tournament_predictions
-- Date: 2026-05-20
-- Purpose: Store extended predictions (group order, best 3rd places, knockout
--          picks) as a single JSONB blob per user per season.

ALTER TABLE tournament_predictions
    ADD COLUMN IF NOT EXISTS bracket_predictions JSONB;

-- Expected shape:
-- {
--   "groups": {"A": [team_id_1st, team_id_2nd, team_id_3rd, team_id_4th], ...},
--   "best_thirds": ["A", "C", "E", "F", "I", "J", "K", "L"],
--   "match_winners": {"M73": team_id, "M74": team_id, ...}
-- }
