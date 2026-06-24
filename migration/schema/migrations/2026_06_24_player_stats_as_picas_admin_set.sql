-- Sticky bit for admin-edited AS picas. When an admin types a picas
-- value in /admin/marca, we set this flag so any subsequent scrape
-- of the same player+matchday won't clobber the manual value — even
-- if the upstream feed (futbolfantasy) later starts publishing a
-- different number for that match.
--
-- The complementary flag for marca_rating is the existing rule in
-- _preserve_admin_marca (keep when current is real and incoming is
-- None/SC), which works for marca because the scrape NEVER returns
-- a real marca rating for tournaments. AS picas can come back from
-- the scrape as either real values or empty, so we need an explicit
-- flag instead of relying on value shape.

ALTER TABLE player_stats
  ADD COLUMN IF NOT EXISTS as_picas_admin_set BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN player_stats.as_picas_admin_set IS
  'TRUE when as_picas was set or last edited by an admin via /admin/marca. Scrapes preserve as_picas while this flag is TRUE so a flaky AS feed cannot overwrite manual edits.';
