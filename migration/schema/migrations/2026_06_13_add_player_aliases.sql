-- Add players.aliases for the Marca cromo matcher.
-- Used to resolve nickname/real-name pairs that the scrape can't link
-- on its own — e.g. "Kaku" (futbolfantasy display_name) <->
-- "Alejandro Romero Gamarra" (the name Marca prints on the cromo).
-- The scrape NEVER writes to this column. Admins fill it manually,
-- typically with the real or alternate name(s) of a player.
--
-- Lookup pattern in marca_preview:
--   token_set(display_name) UNION token_set(aliases)

ALTER TABLE players
  ADD COLUMN IF NOT EXISTS aliases VARCHAR(255);

COMMENT ON COLUMN players.aliases IS
  'Optional comma- or space-separated alternate names (real name, nickname, etc). Used by the Marca cromo matcher to recognise players who appear under a different name on the cromo than in futbolfantasy.';
