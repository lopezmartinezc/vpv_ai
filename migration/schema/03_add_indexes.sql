-- =============================================================================
-- Performance indexes for dashboard queries
-- =============================================================================

-- Matchdays: filter by season + stats_ok (matchday list), season + counts (standings)
CREATE INDEX IF NOT EXISTS idx_matchdays_season ON matchdays(season_id);
CREATE INDEX IF NOT EXISTS idx_matchdays_season_counts ON matchdays(season_id, counts);

-- Participant matchday scores: join on matchday_id + participant_id
CREATE INDEX IF NOT EXISTS idx_pms_matchday ON participant_matchday_scores(matchday_id);
CREATE INDEX IF NOT EXISTS idx_pms_participant ON participant_matchday_scores(participant_id);

-- Lineups: lookup by matchday (for copa and matchday detail queries)
CREATE INDEX IF NOT EXISTS idx_lineups_matchday ON lineups(matchday_id);

-- Lineup players: lookup by lineup_id (already has unique constraint but explicit index helps)
CREATE INDEX IF NOT EXISTS idx_lineup_players_lineup ON lineup_players(lineup_id);

-- Matches: lookup by matchday_id
CREATE INDEX IF NOT EXISTS idx_matches_matchday ON matches(matchday_id);
