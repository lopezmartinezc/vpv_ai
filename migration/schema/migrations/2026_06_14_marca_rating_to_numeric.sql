-- Unify marca_rating / as_picas to numeric strings ("1"-"4").
--
-- Liga seasons already store ratings as "1"…"4" (sin decimales —
-- confirmado en 00_create_schema.sql comments). The new Mundial
-- flow (/admin/marca + cromo OCR) was writing Unicode stars,
-- which complicated every aggregation query (AVG / SORT) with a
-- CASE table. Migrating the few Mundial rows to numeric matches
-- the historic format and lets us drop the Unicode branches from
-- analytics queries.
--
-- "SC", "-" and NULL stay unchanged. Idempotent: re-running the
-- script on already-numeric data is a no-op (WHERE clause excludes
-- non-Unicode rows).

UPDATE player_stats
SET marca_rating = CASE marca_rating
    WHEN '★'    THEN '1'
    WHEN '★★'   THEN '2'
    WHEN '★★★'  THEN '3'
    WHEN '★★★★' THEN '4'
    ELSE marca_rating
END
WHERE marca_rating IN ('★', '★★', '★★★', '★★★★');

UPDATE player_stats
SET as_picas = CASE as_picas
    WHEN '★'    THEN '1'
    WHEN '★★'   THEN '2'
    WHEN '★★★'  THEN '3'
    WHEN '★★★★' THEN '4'
    ELSE as_picas
END
WHERE as_picas IN ('★', '★★', '★★★', '★★★★');
