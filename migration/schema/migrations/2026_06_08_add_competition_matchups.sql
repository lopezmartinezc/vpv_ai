-- Migration: add competition_matchups table for playoff format
-- Date: 2026-06-08
-- Purpose: store the per-jornada head-to-head cruces between VPV
--          participants that make up a playoff. Format-agnostic — the
--          actual format (balanced, groups, Berger, etc.) is described
--          by `competitions.config.format_id` and the matchups follow
--          whatever shape the format plugin generates.

CREATE TABLE IF NOT EXISTS competition_matchups (
    id                    SERIAL PRIMARY KEY,
    competition_id        INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    phase                 VARCHAR(20) NOT NULL,
    group_label           VARCHAR(10),
    round_label           VARCHAR(20),
    round_number          SMALLINT NOT NULL,
    matchday_id           INTEGER REFERENCES matchdays(id) ON DELETE SET NULL,
    participant_a_id      INTEGER REFERENCES season_participants(id) ON DELETE SET NULL,
    participant_b_id      INTEGER REFERENCES season_participants(id) ON DELETE SET NULL,
    feeder_a_id           INTEGER REFERENCES competition_matchups(id),
    feeder_b_id           INTEGER REFERENCES competition_matchups(id),
    score_a               INTEGER,
    score_b               INTEGER,
    winner_participant_id INTEGER REFERENCES season_participants(id) ON DELETE SET NULL,
    CONSTRAINT chk_pair_distinct CHECK (
        participant_a_id IS NULL OR participant_b_id IS NULL OR participant_a_id <> participant_b_id
    )
);

CREATE INDEX IF NOT EXISTS idx_matchups_competition ON competition_matchups(competition_id);
CREATE INDEX IF NOT EXISTS idx_matchups_matchday    ON competition_matchups(matchday_id);
