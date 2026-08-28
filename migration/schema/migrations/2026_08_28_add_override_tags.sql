-- Admin-only player tags on the draft board, stored alongside the manual
-- override (per season + player). Fixed set: titular / suplente / penaltis /
-- lesion / objetivo / evitar. They adjust the draft Priority (not VORP).
-- Idempotent.
ALTER TABLE draft_value_overrides
    ADD COLUMN IF NOT EXISTS tags TEXT[];
