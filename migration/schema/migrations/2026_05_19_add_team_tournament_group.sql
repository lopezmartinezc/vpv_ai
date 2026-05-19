-- Migration: tournament_group on teams for tournament group stage
-- Date: 2026-05-19
-- Purpose: Mundial 2026 (and future tournaments) need to assign teams to groups
--          (A, B, C, ...). Nullable — irrelevant for kind='league' seasons.

ALTER TABLE teams
    ADD COLUMN IF NOT EXISTS tournament_group VARCHAR(2);

CREATE INDEX IF NOT EXISTS idx_teams_tournament_group
    ON teams(season_id, tournament_group);
