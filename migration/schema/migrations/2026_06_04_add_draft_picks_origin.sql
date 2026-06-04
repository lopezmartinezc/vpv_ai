-- Migration: add origin column to draft_picks
-- Date: 2026-06-04
-- Purpose: distinguish manual picks (chosen via UI by the participant or
--          admin) from automatic picks resolved by the wishlist engine.
--          The UI shows a tag for 'auto' and post-mortem queries can
--          count how many picks were resolved without human input.

ALTER TABLE draft_picks
    ADD COLUMN IF NOT EXISTS origin VARCHAR(10) NOT NULL DEFAULT 'manual';
