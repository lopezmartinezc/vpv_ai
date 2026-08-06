-- Per-matchday team on player_stats.
--
-- players.team_id is the player's CURRENT team (for the marca roster, the
-- draft pool, opponent display). Historical per-matchday facts — chiefly
-- home/away derivation for splits — used to be computed from that mutable
-- value, so a mid-season transfer would retroactively mislabel a player's
-- earlier matchdays. player_stats.team_id pins the team the player played
-- for THAT matchday, set at scrape time and never overwritten on re-scrape,
-- so updating the current team can never rewrite history.
--
-- Idempotent: safe to re-run.

ALTER TABLE player_stats
    ADD COLUMN IF NOT EXISTS team_id INT REFERENCES teams(id);

CREATE INDEX IF NOT EXISTS idx_player_stats_team ON player_stats(team_id);

-- Backfill existing rows from the player's current team. Correct for every
-- player who has not changed teams (the vast majority); the handful who did
-- keep whatever the old team_id-based logic already showed, so this is no
-- worse than before. Only fills NULLs, so re-running is safe.
UPDATE player_stats ps
SET team_id = p.team_id
FROM players p
WHERE ps.player_id = p.id
  AND ps.team_id IS NULL;
