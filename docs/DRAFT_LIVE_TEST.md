# Draft en vivo — Entorno de pruebas

Instrucciones para crear un entorno controlado para probar el draft en vivo
sin afectar la temporada real (2025-2026).

## Crear entorno de pruebas

Ejecutar en produccion con `psql -U vpv -d ligavpv`:

```sql
-- ============================================================
-- 1. Crear temporada de prueba
-- ============================================================
INSERT INTO seasons (name, status, matchday_start, matchday_end, matchday_current, draft_pool_size, lineup_deadline_min, total_participants)
VALUES ('TEST-2027', 'draft', 1, 38, 0, 26, 30, 0)
RETURNING id;
-- Anotar el ID devuelto (ej: 9). Usarlo abajo como @TEST_SEASON_ID

-- ============================================================
-- 2. Copiar equipos de la temporada actual (season_id = 8)
-- ============================================================
INSERT INTO teams (season_id, name, short_name, slug, logo_path)
SELECT
    (SELECT id FROM seasons WHERE name = 'TEST-2027'),
    name, short_name, slug, logo_path
FROM teams
WHERE season_id = 8;

-- ============================================================
-- 3. Copiar jugadores (sin owner, todos disponibles)
--    Vinculados a los equipos nuevos por slug
-- ============================================================
INSERT INTO players (season_id, team_id, name, display_name, slug, position, photo_path, source_url, is_available)
SELECT
    t_new.season_id,
    t_new.id,
    p.name,
    p.display_name,
    p.slug,
    p.position,
    p.photo_path,
    p.source_url,
    TRUE
FROM players p
JOIN teams t_old ON p.team_id = t_old.id AND t_old.season_id = 8
JOIN teams t_new ON t_new.slug = t_old.slug AND t_new.season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027');

-- ============================================================
-- 4. Añadir participantes (todos los usuarios activos)
-- ============================================================
INSERT INTO season_participants (season_id, user_id, draft_order, is_active)
SELECT
    (SELECT id FROM seasons WHERE name = 'TEST-2027'),
    u.id,
    ROW_NUMBER() OVER (ORDER BY u.id),
    TRUE
FROM users u
WHERE u.password_hash IS NOT NULL AND u.password_hash != '';

-- Actualizar total_participants
UPDATE seasons
SET total_participants = (
    SELECT COUNT(*) FROM season_participants
    WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027')
)
WHERE name = 'TEST-2027';

-- ============================================================
-- 5. Crear draft de pretemporada
-- ============================================================
INSERT INTO drafts (season_id, draft_type, phase, status)
VALUES (
    (SELECT id FROM seasons WHERE name = 'TEST-2027'),
    'snake',
    'preseason',
    'pending'
)
RETURNING id;
-- Anotar el ID devuelto (ej: 20). Este es el draft_id para la URL
```

## Probar

1. Desplegar el codigo con el draft en vivo
2. Ir a `/drafts/gestionar`, seleccionar temporada "TEST-2027"
3. Click en "Draft en vivo" (boton verde)
4. O directamente: `/drafts/live/{draft_id}`
5. Compartir la URL con otros usuarios para probar multijugador
6. Los picks se guardan SOLO en la temporada TEST-2027

## Verificar

```sql
-- Ver picks del draft de prueba
SELECT dp.pick_number, dp.round_number, u.display_name, p.display_name AS player, p.position
FROM draft_picks dp
JOIN drafts d ON dp.draft_id = d.id
JOIN season_participants sp ON dp.participant_id = sp.id
JOIN users u ON sp.user_id = u.id
JOIN players p ON dp.player_id = p.id
WHERE d.season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027')
ORDER BY dp.pick_number;
```

## Limpiar (borrar todo el entorno de pruebas)

```sql
-- Borrar en orden de dependencias
DELETE FROM draft_picks WHERE draft_id IN (SELECT id FROM drafts WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027'));
DELETE FROM drafts WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027');
DELETE FROM players WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027');
DELETE FROM season_participants WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027');
DELETE FROM teams WHERE season_id = (SELECT id FROM seasons WHERE name = 'TEST-2027');
DELETE FROM seasons WHERE name = 'TEST-2027';
```

## Notas

- La temporada TEST-2027 tiene status 'draft' — no afecta al scraping (solo la temporada 'active' se scrapea)
- Los jugadores son copias sin owner — todos disponibles para el draft
- Los participantes son los mismos usuarios reales (necesitan estar logueados)
- Los picks se guardan en la BD pero solo bajo la temporada TEST-2027
- El selector de temporada en la web mostrara "TEST-2027" como opcion
- Al terminar, ejecutar el script de limpieza para borrar todo
