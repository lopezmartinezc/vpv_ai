-- Marca cromo aliases: nombres que Marca imprime y que el scrape de
-- futbolfantasy no recoge como display_name.
--
-- 1. Amad Traoré (Costa de Marfil, MED) — Marca imprime "A. Diallo"
--    porque el jugador es conocido como "Amad Diallo" (Manchester
--    United). futbolfantasy usa solo "Amad Traoré".
--
-- 2. Mohamed Belhadj Mahmoud (Túnez, MED) — Marca imprime "Belhadj",
--    futbolfantasy usa el nombre completo. El matcher necesita el
--    apellido corto.

UPDATE players SET aliases = 'Diallo'  WHERE id = 6981 AND aliases IS NULL;
UPDATE players SET aliases = 'Belhadj' WHERE id = 7113 AND aliases IS NULL;
