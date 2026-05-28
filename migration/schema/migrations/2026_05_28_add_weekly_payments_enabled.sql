-- Migration: add weekly_payments_enabled to seasons
-- Date: 2026-05-28
-- Purpose: per-season toggle for the "weekly payment by position" mechanic.
--          Until now it was derived from season.kind ('league' -> on,
--          'tournament' -> off). Some tournaments may want to opt in
--          (a long cup, an exhibition league played as a tournament...),
--          so we make it explicit. Default for new league seasons is true,
--          for new tournament seasons is false.

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS weekly_payments_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill existing league seasons (the column default applies to tournaments).
UPDATE seasons
SET    weekly_payments_enabled = TRUE
WHERE  kind = 'league'
  AND  weekly_payments_enabled = FALSE;
