-- Knockout penalty-shootout winner override.
--
-- KO matches decided on penalties end level on the pitch (home_score ==
-- away_score), so the bracket can't tell who advances from the score alone.
-- Player fantasy points are unaffected (the draw is the real result); this
-- column ONLY drives knockout bracket progression.
--
-- Idempotent: safe to re-run.

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS ko_winner_team_id INT REFERENCES teams(id);
