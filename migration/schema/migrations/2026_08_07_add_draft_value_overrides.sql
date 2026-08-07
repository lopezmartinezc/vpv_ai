-- Manual draft-value overrides (shared, admin-set) for the preseason board.
--
-- The draft board projects each player's value from history/current stats,
-- but the organiser needs to override that value by hand — especially for
-- brand-new players (no history to project from) and players whose role
-- changed (new club / new position). A direct manual value (pts/match)
-- replaces the automatic projection when set; a free-text note explains why.
-- Shared across the season (one board), keyed by (season, player).
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS draft_value_overrides (
    id           SERIAL PRIMARY KEY,
    season_id    INTEGER NOT NULL REFERENCES seasons(id),
    player_id    INTEGER NOT NULL REFERENCES players(id),
    manual_value NUMERIC(5, 2),
    note         TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_draft_value_override UNIQUE (season_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_value_overrides_season
    ON draft_value_overrides (season_id);
