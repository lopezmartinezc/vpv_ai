-- Migration: add tournament fields to seasons
-- Date: 2026-05-19
-- Purpose: Support Mundial 2026 (and future tournaments) as season with kind='tournament'
--          plus tournament_type discriminator and JSONB config for groups/knockout structure.

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'league',
    ADD COLUMN IF NOT EXISTS tournament_type VARCHAR(30),
    ADD COLUMN IF NOT EXISTS tournament_config JSONB,
    ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50);

-- Add a CHECK constraint for kind values (only if not already present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'seasons_kind_check'
    ) THEN
        ALTER TABLE seasons
            ADD CONSTRAINT seasons_kind_check
            CHECK (kind IN ('league', 'tournament'));
    END IF;
END $$;

-- Index for filtering tournaments separately
CREATE INDEX IF NOT EXISTS idx_seasons_kind ON seasons(kind);
