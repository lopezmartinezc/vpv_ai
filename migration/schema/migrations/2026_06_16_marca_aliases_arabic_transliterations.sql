-- Marca aliases for transliteration mismatches surfaced by the
-- Mundial 2026 cromo testing campaign (Bélgica-Egipto, Saudí-Uruguay).
-- Marca and futbolfantasy don't agree on how to romanise certain
-- Arabic names, and Marca occasionally drops a letter or swaps
-- consonants in Western names too. Each alias is the surname form the
-- cromo prints.
--
-- 1. Marwan Ateya (Egipto, MED) — Marca writes "Attia".
-- 2. Mostafa Ziko (Egipto, DEL) — Marca writes "Zico" (silent k).
-- 3. Abdullah Al-Hamdan (Saudí, DEL) — Marca writes "Handam"
--    (metathesis: Hamdan -> Handam).
-- 4. Guillermo Varela (Uruguay, DEF) — Marca writes "Valera"
--    (l/r consonant swap).

UPDATE players SET aliases = 'Attia'   WHERE id = 7168 AND aliases IS NULL;
UPDATE players SET aliases = 'Zico'    WHERE id = 7174 AND aliases IS NULL;
UPDATE players SET aliases = 'Handam'  WHERE id = 7250 AND aliases IS NULL;
UPDATE players SET aliases = 'Valera'  WHERE id = 7287 AND aliases IS NULL;
