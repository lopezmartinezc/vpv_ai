-- Migration: add edit_unlocked column to seasons
-- Date: 2026-05-05
-- Purpose: Allow admin to override the lock on finished seasons

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS edit_unlocked BOOLEAN NOT NULL DEFAULT FALSE;
