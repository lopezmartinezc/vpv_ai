-- Migration: tournament_predictions table
-- Date: 2026-05-19
-- Purpose: Allow each participant to predict tournament winner, top scorer, etc.
--          Stores predictions made BEFORE the tournament starts. Bonus points
--          awarded at the end when comparing predictions vs reality.

CREATE TABLE IF NOT EXISTS tournament_predictions (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    user_id         INT          NOT NULL REFERENCES users(id),
    winner_team_id  INT          REFERENCES teams(id),
    top_scorer_player_id INT     REFERENCES players(id),
    best_player_id  INT          REFERENCES players(id),
    dark_horse_team_id INT       REFERENCES teams(id),  -- "sorpresa" del torneo
    notes           VARCHAR(500),
    bonus_points    SMALLINT     NOT NULL DEFAULT 0,
    submitted_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(season_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_tournament_predictions_season
    ON tournament_predictions(season_id);
