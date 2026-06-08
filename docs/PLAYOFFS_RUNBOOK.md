# Playoffs — Runbook operativo

Guía paso a paso para gestionar un playoff en producción. Para el diseño y la arquitectura ver [PLAYOFFS_DESIGN.md](PLAYOFFS_DESIGN.md). Para la guía de añadir formatos nuevos ver [PLAYOFFS_DEV_GUIDE.md](PLAYOFFS_DEV_GUIDE.md).

---

## Prerequisitos

- Migración `2026_06_08_add_competition_matchups.sql` aplicada.
- Backend reiniciado con la versión que incluye `features/competitions/`.
- Frontend rebuildeado (la página `/playoffs` y la tarjeta admin son nuevas).
- Una season tipo `tournament` con sus 13 participantes activos y matchdays creados en BBDD.

Verificación rápida:

```bash
# Backend operativo y formato disponible
curl -sf https://new.ligavpv.com/api/competitions/formats | jq

# Esperado:
# [{"format_id":"balanced_ko4","display_name":"Balanced (4 partidos/uno) + KO top-4",
#   "n_rounds_regular":6,"n_rounds_ko":2}]
```

---

## Crear un playoff

### Via UI (recomendado)

1. Login como admin → `/admin/temporadas`.
2. Expandir la season (Mundial 2026).
3. Tarjeta **"Playoffs"** → seleccionar formato (v1 sólo `balanced_ko4`).
4. **"Crear Playoff"** → la competition queda en estado `pending`.

### Via curl

```bash
TOKEN="<jwt admin>"
SEASON_ID=11

curl -sf -X POST "https://new.ligavpv.com/api/competitions/admin/season/${SEASON_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"format_id":"balanced_ko4"}' | jq
```

Idempotente: si ya existe un playoff para la season, devuelve el existente.

---

## Generar la fase regular

Define el rango de jornadas. Para `balanced_ko4` son **6 jornadas exactas**.

### Via UI

1. Tarjeta Playoffs en `/admin/temporadas`.
2. Input `Jornada inicio` (la `Jornada fin` se calcula sola desde el formato).
3. Input `Jornadas KO` (pre-rellenado con `start+6, start+7`, editable).
4. **"Generar calendario"** → inserta los 26 cruces regular y persiste las
   jornadas KO planificadas. Cuando se resuelva la última jornada regular, el
   KO arrancará solo. **No hace falta volver a la tarjeta.**

### Via curl

```bash
COMP_ID=$(curl -sf "https://new.ligavpv.com/api/competitions/season/${SEASON_ID}" \
  -H "Authorization: Bearer ${TOKEN}" | jq -r '.competitions[] | select(.type=="playoff") | .id')

curl -sf -X POST "https://new.ligavpv.com/api/competitions/admin/${COMP_ID}/start-regular" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "matchday_start": 1,
    "matchday_end": 6,
    "planned_ko_matchday_numbers": [7, 8]
  }' | jq
```

Respuesta: `{"matchups_inserted":26}`. El sorteo aleatorio queda persistido en
`competitions.config.seed`. Las jornadas KO planificadas se guardan en
`competitions.config.planned_ko_matchday_numbers` y se ejecutan
**automáticamente** cuando la fase regular acaba (vía
`recalculate_matchups_for_matchday`).

Si omites `planned_ko_matchday_numbers`, el comportamiento es el legacy: hay
que llamar manualmente a `start-ko` tras la última jornada regular.

### Verificación SQL

```sql
SELECT round_number, COUNT(*) AS cruces
FROM competition_matchups
WHERE competition_id = <COMP_ID>
  AND phase = 'regular'
GROUP BY round_number
ORDER BY round_number;

-- Esperado: 5, 5, 5, 5, 3, 3 (suma = 26)

SELECT participant_a_id, COUNT(*) AS partidos
FROM (
  SELECT participant_a_id FROM competition_matchups WHERE competition_id = <COMP_ID> AND phase='regular'
  UNION ALL
  SELECT participant_b_id FROM competition_matchups WHERE competition_id = <COMP_ID> AND phase='regular'
) sub
GROUP BY participant_a_id
ORDER BY participant_a_id;

-- Esperado: cada participant_id aparece exactamente 4 veces
```

---

## La fase regular avanza sola

Cada vez que se scrapea una jornada que esté en el rango del playoff, el `ScoreAggregator` invoca automáticamente `CompetitionService.recalculate_matchups_for_matchday`. Sin intervención manual:

- Lee `participant_matchday_scores.total_points` de los 2 participantes del cruce.
- Asigna `score_a`, `score_b`, `winner_participant_id`.
- En empate de fase regular: `winner_participant_id = NULL` y los dos suman 1 pt.

Si algo falla, queda log con prefijo `competition matchup recalc failed`. El scraping NO se rompe (hook best-effort).

### Forzar recálculo manual

Si tras un cambio de `match.counts` (o algún ajuste retroactivo) necesitas recalcular:

```bash
# Re-scrapea la jornada — el hook del aggregator se dispara solo
cd /opt/vpv/backend
sudo -u vpv .venv/bin/python -m src.features.scraping.cli scrape-matchday 11 3
```

---

## Iniciar las eliminatorias

Cuando la fase regular tiene **todos los 26 cruces resueltos** (cada uno con `score_a` y `score_b`), arranca el KO.

### Via UI

1. Tarjeta Playoffs → ahora muestra inputs `Jornadas KO`.
2. Para `balanced_ko4` necesitas **2 jornadas** separadas por coma. Para el Mundial: `7,8` (semis en J7, final en J8).
3. **"Iniciar eliminatorias"** → se crean 2 semis con participantes ya asignados (top-4 cruzados) + 1 final con feeders.

### Via curl

```bash
curl -sf -X POST "https://new.ligavpv.com/api/competitions/admin/${COMP_ID}/start-ko" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"ko_matchday_numbers":[7,8]}' | jq
```

Si quedan cruces regular sin resolver, devuelve 400 con `Quedan N cruces de fase regular sin resolver`.

### Comportamiento de los empates en KO

- Si J7 termina con `score_a == score_b` en una semi, **gana el mejor `rank`** de la fase regular (snapshot persistido en `config.regular_standings_snapshot`).
- La final: misma regla.

### Cierre automático

Cuando se scrapea J8, el aggregator marca el cruce final con su `winner_participant_id`. Si el resultado deja un campeón claro, la competition pasa a `status='completed'` automáticamente.

---

## Cosas que pueden ir mal y cómo arreglarlas

### "El formato balanced_ko4 requiere 6 jornadas, recibidas N"

Pasaste un rango incorrecto. Ajusta `matchday_start` y `matchday_end` para que el rango sea exactamente 6.

### "Empate sin desempate dentro del top-4 del playoff"

Dos o más participantes acabaron la fase regular con **idénticos puntos e
idéntica diferencia acumulada**, y caen dentro del corte que decide qué top-4
entra al KO. El sistema rechaza iniciar el KO porque cualquier orden sería
arbitrario.

Resolución manual (cuando aparezca):

```sql
-- Ver el empate
SELECT rank, points, diff_avg, display_name
FROM (
  -- query equivalente al cálculo del backend
  SELECT p.id AS pid, u.display_name,
         /* tus puntos y diff_avg */
  FROM ...
) AS s
ORDER BY points DESC, diff_avg DESC;
```

Opciones:
1. **Esperar más jornadas** — si la temporada permite añadir una más.
2. **Resolver por sorteo / acuerdo** y editar `competitions.config` para forzar
   el orden:
   ```sql
   UPDATE competitions
   SET config = jsonb_set(
       config,
       '{tie_breaker_overrides}',
       '{"<participant_id>": <forced_rank>}'::jsonb
   )
   WHERE id = <COMP_ID>;
   ```
   (Esta override no se aplica automáticamente todavía; v2 la usará. Por ahora
   sirve como registro documentado.)
3. **Forzar uno de los dos** vía SQL directo en el config + reintento del
   `start-ko`.

### "Quedan N cruces de fase regular sin resolver"

Algún cruce de la fase regular no tiene scores. Causa habitual: el aggregator no se ha ejecutado para esa jornada (scraping pendiente).

```sql
SELECT round_number, participant_a_id, participant_b_id, matchday_id
FROM competition_matchups
WHERE competition_id = <COMP_ID>
  AND phase = 'regular'
  AND score_a IS NULL
  AND participant_b_id IS NOT NULL;
```

Solución: scrapear esa jornada con `scrape-matchday`.

### Necesito anular el sorteo y volver a tirar dados

Borrar los cruces actuales y dejar la competition en `pending`:

```sql
DELETE FROM competition_matchups WHERE competition_id = <COMP_ID>;
UPDATE competitions
SET status = 'pending',
    config = config - 'seed' - 'matchday_range_regular'
WHERE id = <COMP_ID>;
```

Luego en UI o curl: re-llamar `start-regular`.

### Necesito tirar el playoff entero y empezar de cero

```sql
DELETE FROM competition_matchups WHERE competition_id = <COMP_ID>;
DELETE FROM competitions WHERE id = <COMP_ID>;
```

Vuelve a "Crear Playoff" en la UI.

### El admin se equivocó eligiendo formato y aún no hay cruces

Sólo aplica si está en `status='pending'`. Borra y recrea:

```sql
DELETE FROM competitions WHERE id = <COMP_ID> AND status = 'pending';
```

### El admin se equivocó tras start-regular

Hay cruces ya, pero la temporada no avanzó. Usa el caso "Anular sorteo" arriba para dejarlo en `pending`, y luego recrea con el formato nuevo.

---

## Verificación end-to-end manual

Tras `start-regular`:

```sql
-- Counts y distribuciones
SELECT phase, round_number, COUNT(*) FROM competition_matchups
WHERE competition_id = <COMP_ID> GROUP BY phase, round_number ORDER BY phase, round_number;
```

Tras 1ª jornada scrapeada:

```sql
-- Resultados asignados
SELECT round_number, matchday_id, score_a, score_b, winner_participant_id
FROM competition_matchups
WHERE competition_id = <COMP_ID>
  AND matchday_id = (SELECT id FROM matchdays WHERE season_id=<SEASON> AND number=1);
```

Tras `start-ko`:

```sql
-- Cuartos/semis/final creados
SELECT round_label, round_number, participant_a_id, participant_b_id, feeder_a_id, feeder_b_id
FROM competition_matchups
WHERE competition_id = <COMP_ID> AND phase='ko'
ORDER BY round_number, id;
```

Tras J8 scrapeada:

```sql
-- Final con ganador y status completed
SELECT status FROM competitions WHERE id = <COMP_ID>;
-- 'completed'

SELECT winner_participant_id
FROM competition_matchups
WHERE competition_id = <COMP_ID> AND round_label='final';
```
