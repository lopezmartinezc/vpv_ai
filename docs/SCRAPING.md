# Sistema de Scraping — Liga VPV Fantasy

## Vision general

El sistema obtiene datos de **futbolfantasy.com** (unica fuente) y los almacena en PostgreSQL. Cubre tres funciones:

1. **Estadisticas de jugadores** — puntos, goles, asistencias, tarjetas, etc. por jornada
2. **Calendario de partidos** — resultados y fechas actualizadas de La Liga
3. **Deteccion de cambios** — CRC per-match para re-scrapear solo cuando hay datos nuevos

## Arquitectura

```
                    futbolfantasy.com
                          |
                    [ScrapingClient]         httpx async + retry + delay
                          |
              +-----------+-----------+
              |           |           |
         [parsers.py] [parsers.py] [parsers.py]
         player_stats   calendar    match_crc
              |           |           |
         [ScoringEngine]  |           |
              |           |           |
         [ScrapingService]            |
              |                       |
         [ScrapingRepository]         |
              |                       |
         [PostgreSQL]            [scheduler.py]
                                      |
                              APScheduler (2 jobs)
                              - tick: cada 15 min
                              - calendar_sync: diario 06:00 UTC
```

## Componentes

### Archivos

```
backend/src/features/scraping/
  __init__.py
  config.py           # ScrapingSettings (env vars)
  client.py           # ScrapingClient (httpx async, retry, delay)
  parsers.py          # 7 parsers: teams, roster, calendar, player_stats,
                      #   homepage_matchday, player_photo, match_crc
  scoring.py          # ScoringEngine — calcula puntos desde scoring_rules
  aggregation.py      # ScoreAggregator — genera participant_matchday_scores
  service.py          # ScrapingService — orquesta workflows
  repository.py       # ScrapingRepository — acceso a DB
  scheduler.py        # APScheduler — 2 jobs automaticos
  photos.py           # PhotoDownloader — descarga fotos WebP
  cli.py              # CLI para ejecucion manual
  router.py           # 8 endpoints FastAPI (+ 3 en seasons/router.py para lifecycle)
```

### Configuracion (`config.py`)

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `SCRAPING_BASE_URL` | `https://www.futbolfantasy.com` | URL base de futbolfantasy |
| `SCRAPING_SEASON_SLUG` | `laliga-25-26` | Slug temporada para URLs de jugadores (fallback; se lee de `seasons.scraping_slug` si existe) |
| `SCRAPING_DELAY_MIN` | `1.0` | Delay minimo entre requests (segundos) |
| `SCRAPING_DELAY_MAX` | `4.0` | Delay maximo entre requests (segundos) |
| `SCRAPING_TIMEOUT` | `15.0` | Timeout por request (segundos) |
| `SCRAPING_MAX_RETRIES` | `3` | Reintentos por request fallido |
| `SCRAPING_POLL_INTERVAL_SECONDS` | `900` | Intervalo entre ticks del scheduler (15 min) |
| `SCRAPING_BUFFER_MINUTES` | `120` | Minutos tras `played_at` para considerar partido terminado |

### Client (`client.py`)

HTTP client async basado en `httpx`:
- User-Agent aleatorio
- Delay aleatorio entre requests (anti-bot)
- Retry con backoff exponencial
- Context manager (`async with ScrapingClient() as client`)

### Parsers (`parsers.py`)

7 funciones puras (HTML in -> datos out):

| Parser | Input | Output | Uso |
|--------|-------|--------|-----|
| `parse_teams(html)` | Homepage | `list[TeamData]` | Obtener equipos La Liga |
| `parse_roster(html)` | Pagina equipo | `list[PlayerUrlData]` | Obtener jugadores + posiciones |
| `parse_calendar(html, season_year)` | Calendario La Liga | `list[CalendarMatchData]` | Resultados + fechas partidos |
| `parse_player_stats(html, matchday)` | Pagina jugador | `PlayerMatchdayStats \| None` | Stats individuales por jornada |
| `parse_homepage_matchday(html)` | Homepage | `HomepageMatchdayInfo \| None` | Jornada actual + CRC |
| `parse_player_photo(html)` | Pagina jugador | `str \| None` | URL foto perfil |
| `parse_match_crc(html)` | Pagina partido | `str` | CRC de ratings (change detection) |

#### Calendar date parsing

La pagina de calendario muestra fechas solo para partidos **pendientes** (no jugados):
- Formato: `"Vie 27/02 21:00h"` (dia_semana DD/MM HH:MMh)
- El ano se infiere de la temporada: meses Ago-Dic = `season_year - 1`, Ene-Jul = `season_year`
- Partidos ya jugados solo muestran resultado, sin fecha

### ScoringEngine (`scoring.py`)

Calcula puntos a partir de `scoring_rules` de la BD (configurable por temporada, por posicion).

Flujo:
1. Recibe `PlayerMatchdayStats` + posicion del jugador
2. Aplica reglas de `scoring_rules` (por `rule_key` + `position`)
3. Retorna `PointsBreakdown` con puntos desglosados

### ScrapingService (`service.py`)

Orquesta los 3 workflows principales:

#### `scrape_matchday(season_id, matchday_number)`

Scrapea estadisticas de TODOS los jugadores de una jornada:

1. Carga `scoring_rules` -> `ScoringEngine`
2. Obtiene `Matchday` + `Match` rows
3. Filtra matches con `counts=True`
4. Para cada match: obtiene jugadores de ambos equipos
5. Para cada jugador: fetch HTML -> parse stats -> calcular puntos -> upsert `player_stats`
6. Si todos los matches OK -> marca `matchday.stats_ok = True`
7. Ejecuta `ScoreAggregator` (genera `participant_matchday_scores`)
8. Actualiza `season.matchday_scanned`

Retorna: `{ processed, skipped, errors }`

#### `scrape_match_players(season_id, matchday_number, match_id)`

Igual que `scrape_matchday` pero para un solo partido. Util para re-scrapear partidos individuales.

#### `scrape_calendar(season_id)`

Actualiza resultados y fechas desde el calendario de La Liga:

1. Obtiene temporada -> extrae ano para URL (`/laliga/calendario/{year}`)
2. Fetch HTML -> `parse_calendar(html, season_year)`
3. Para cada partido:
   - Si tiene `played_at` y cambio -> `update_match_played_at()`
   - Si tiene resultado y cambio -> `update_match_score()`
4. Si cambiaron fechas -> `sync_matchday_first_match_at()` (recalcula `MIN(played_at)`)

Retorna: `{ scores_updated, dates_updated }`

### Scheduler (`scheduler.py`)

APScheduler con 2 jobs:

#### Job 1: `scraping_tick` (interval, cada 15 min)

Deteccion de cambios por CRC per-match:

1. Obtiene temporada activa + `matchday_current`
2. Ejecuta `scrape_calendar()` para actualizar resultados
3. Obtiene matches de la jornada actual
4. Filtra matches jugados (tienen `home_score` + `source_url`)
5. Para cada match jugado: fetch pagina partido -> `parse_match_crc()`
6. Si CRC cambio respecto a `match.stats_crc` -> marca para re-scrape
7. Scrape cada match con CRC cambiado via `scrape_match_players()`

```
[Tick cada 15 min]
  -> scrape_calendar (resultados + fechas)
  -> para cada match jugado:
       -> fetch match page -> CRC
       -> si CRC cambio:
            -> scrape_match_players (stats)
```

#### Job 2: `calendar_sync` (cron, diario 06:00 UTC)

Sincronizacion diaria del calendario:

1. Obtiene temporada activa
2. Ejecuta `scrape_calendar()` (actualiza fechas + resultados)

Esto es importante porque La Liga cambia horarios de partidos con frecuencia.

### Repository (`repository.py`)

Metodos de acceso a datos relevantes para scraping:

| Metodo | Descripcion |
|--------|-------------|
| `get_active_season()` | Temporada con `status='active'` |
| `get_scoring_rules(season_id)` | Reglas puntuacion (formato nested dict) |
| `get_matchday(season_id, number)` | Jornada por numero |
| `get_matches_for_matchday(matchday_id)` | Partidos de una jornada |
| `get_match_by_source_id(source_id)` | Buscar match por ID de futbolfantasy |
| `get_players_for_teams(season_id, team_ids)` | Jugadores de equipos |
| `upsert_player_stat(...)` | INSERT/UPDATE `player_stats` (ON CONFLICT) |
| `update_match_score(match_id, ...)` | Actualizar resultado partido |
| `update_match_played_at(match_id, played_at)` | Actualizar fecha partido |
| `update_match_crc(match_id, stats_crc)` | Guardar CRC de match page |
| `sync_matchday_first_match_at(season_id)` | Recalcular `MIN(played_at)` por jornada |
| `mark_match_stats_ok(match_id)` | Marcar match como scrapeado OK |
| `mark_matchday_stats_ok(matchday_id)` | Marcar jornada como completa |
| `create_team(season_id, name, slug)` | Crear equipo (season init) |
| `create_player(season_id, team_id, ...)` | Crear jugador (season init) |
| `create_match(matchday_id, home_team_id, ...)` | Crear partido (season init) |
| `get_teams_by_season(season_id)` | Listar equipos de temporada |

### Photos (`photos.py`)

`PhotoDownloader` descarga fotos de jugadores:
- Formato: WebP 200x200 (via Pillow)
- Ruta: `static/photos/season_{id}/{slug}.webp`
- Solo descarga jugadores sin `photo_path`
- Delay entre requests para anti-bot

### CLI (`cli.py`)

```bash
# Scrapear jornada actual de la temporada activa
python -m src.features.scraping.cli scrape-current

# Scrapear una jornada especifica
python -m src.features.scraping.cli scrape-matchday 8 25

# Scrapear un partido individual
python -m src.features.scraping.cli scrape-match 8 25 301

# Re-scrapear una temporada entera por jugador (1 fetch por jugador,
# en vez de N por jornada). Pensado para auditoria de fin de temporada.
python -m src.features.scraping.cli scrape-season-full 8 --start 6 --end 38

# Actualizar calendario (resultados + fechas)
python -m src.features.scraping.cli update-calendar 8

# Verificar cambios en homepage (CRC)
python -m src.features.scraping.cli check-updates

# Descargar fotos de jugadores
python -m src.features.scraping.cli download-photos 8
```

#### scrape-season-full (auditoria de temporada)

La pagina de un jugador en futbolfantasy contiene TODAS las jornadas en una sola
tabla. `scrape-season-full` aprovecha esto: 1 fetch por jugador (~770 fetches)
en vez de N fetches por jornada (~13.000+ para una temporada completa).
~30 min vs ~10h.

Flujo:
1. Lista todos los `players` de la temporada.
2. Por cada jugador: `GET /jugadores/{slug}`, parsea TODAS las filas
   `tr.plegado` de la tabla de stats.
3. Para cada (jugador, jornada): upsert en `player_stats`.
   - Si la fila ya existe: **preserva** `position` y `match_id` historicos.
   - Si es nueva: usa `player.position` actual y resuelve `match_id` via
     `find_match_for_team(matchday_id, player.team_id)`.
4. Llama `aggregate_matchday` una vez por cada jornada afectada para
   recalcular `lineup_players.points` -> `lineups.total_points` ->
   `participant_matchday_scores`.

**Backup obligatorio antes de usar** (ver "Auditoria de fin de temporada" abajo).

## Flujo de datos completo

### Inicio de temporada

Automatizado via `POST /api/seasons/admin/initialize`:
```
1. Crear temporada con scraping_slug (endpoint initialize)
   -> copia scoring_rules, payments, participants del source
   -> crea 38 matchdays vacios
2. Background task automatico:
   -> scrape teams (homepage) -> crear equipos La Liga
   -> scrape rosters (por equipo) -> crear jugadores
   -> scrape calendar -> crear matches con fechas/equipos
3. POST /seasons/admin/{id}/download-photos -> fotos WebP
```

Alternativa manual (CLI):
```
1. Crear temporada en BD (admin)
2. scrape teams -> obtener equipos La Liga
3. scrape rosters -> obtener jugadores por equipo
4. update-calendar -> crear/actualizar partidos con fechas
5. download-photos -> fotos de jugadores
```

### Durante la temporada (automatico)

```
Cada 15 minutos (scheduler tick):
  1. scrape_calendar -> actualizar resultados pendientes
  2. Para cada match jugado con CRC cambiado:
     - scrape_match_players -> stats + puntos
     - aggregate_matchday -> participant_matchday_scores

Cada dia a las 06:00 UTC (calendar_sync):
  1. scrape_calendar -> actualizar fechas reprogramadas por La Liga

Cada 60 segundos (deadline_check):
  1. Si deadline superado -> copiar alineacion anterior para participantes sin alineacion

Cada 60 segundos (deadline_reminder):
  1. Si faltan ~2h o ~30min para el deadline:
     - Enviar mensaje Telegram al grupo de alertas (TELEGRAM_ALERTS_CHAT_ID)
     - Enviar push notification a usuarios sin alineacion
     - Solo a participantes que NO han enviado alineacion
```

### Panel de admin

El admin puede:
- **Iniciar/detener** el scheduler
- **Forzar tick** manual
- **Scrapear jornada/partido** especifico
- **Actualizar calendario** manualmente
- Ver estado del scheduler, ultimo tick, proximo tick, ultimo/proximo calendar sync

## URLs scrapeadas

| URL | Datos | Parser |
|-----|-------|--------|
| `futbolfantasy.com` | Homepage — jornada actual, CRC | `parse_homepage_matchday` |
| `futbolfantasy.com/laliga/calendario/{year}` | Calendario completo La Liga | `parse_calendar` |
| `futbolfantasy.com/jugadores/{slug}` | Stats jugador (todas las jornadas) | `parse_player_stats`, `parse_player_all_matchdays` |
| `futbolfantasy.com/partidos/{id}-{home}-{away}` | Pagina partido — score, CRC ratings | `parse_match_score`, `parse_match_crc` |
| `futbolfantasy.com/laliga/equipos/{team-slug}` | Plantilla equipo | `parse_roster` (legacy, ver bugs 2026-05) |

**Nota sobre URLs (cambios mayo 2026)**: futbolfantasy migro los formatos de
URL. El partido ahora exige slug `{home}-{away}` despues del id; la pagina de
jugador ya no acepta el sufijo `/{season_slug}`. Las URLs de la BD se
autocorrigen en el siguiente tick del scheduler (campo `urls_updated` en el
log de `scrape_calendar`).

## Deteccion de cambios (CRC)

Dos niveles de CRC:

1. **Homepage CRC** (legacy, deprecated): CRC de toda la seccion de jornada actual. Poco fiable — cambia por cualquier razon.

2. **Per-match CRC** (actual): Para cada partido jugado, calcula CRC de los ratings `modo-picas` + `cronistas-marca` de la pagina del partido. Solo dispara re-scrape cuando los ratings de ese partido especifico cambian. Almacenado en `matches.stats_crc`.

## Notas importantes

- **Rate limiting**: Delay aleatorio 1-4s entre requests. El sistema scrapea ~40-50 jugadores por partido (2 equipos x ~25 jugadores). Una jornada completa (10 partidos) puede tardar 30-60 minutos.
- **Idempotencia**: `upsert_player_stat` usa `ON CONFLICT (player_id, matchday_id)` — re-scrapear es seguro.
- **Posicion historica preservada**: `player_stats.position` es la fuente de
  verdad para puntos (un jugador puede cambiar de posicion en el draft de
  invierno, lo que altera la formula de goles e imbatibilidad). Los 3 flujos
  de scraping (`scrape_matchday`, `scrape_match_players`,
  `scrape_season_by_player`) preservan `position` y `match_id` cuando la fila
  `(player_id, matchday_id)` ya existe; solo asignan valores nuevos en filas
  inexistentes. Asi, re-scrapear despues de un cambio de posicion o de equipo
  NO altera la verdad historica de jornadas pasadas.
- **Counts a 2 niveles**: `matchdays.counts` Y `matches.counts` determinan si un partido/jornada computa para la clasificacion. El scraping procesa todos los matches con `counts=True`.
- **Fechas del calendario**: Solo los partidos pendientes tienen fecha en el HTML. Los ya jugados no muestran fecha, solo resultado. Las fechas ya almacenadas en BD para partidos jugados son las originales de la migracion.

## Bugs corregidos (2026-03-17)

1. **Parser roto**: futbolfantasy.com cambio de 3 `div.inside_tab` a 2. Parser ahora usa `div.puntos` como ancla.
2. **stats_ok prematuro**: Se marcaba `stats_ok=true` cuando `total_processed=0` (stats no disponibles aun). Ahora requiere `processed > 0`.
3. **CRC diferido**: CRC se guardaba antes de confirmar que el scraping tuvo exito. Ahora solo se persiste si se procesaron stats.
4. **404 = skip**: Un jugador con 404 en futbolfantasy bloqueaba todo el partido. Ahora se trata como skip.
5. **No retry 4xx**: El client reintentaba 404/403 tres veces. Ahora solo reintenta errores 5xx.

## Bugs corregidos (2026-05-25/26)

1. **URL partido nuevo formato** (`c6691e5`): `/partidos/{id}` empezo a devolver
   404. futbolfantasy ahora exige slug: `/partidos/{id}-{home}-{away}`. Fix:
   `import_teams_and_players` usa `cal_match.source_url` (que el parser ya
   extrae con slug del calendario); `scrape_calendar` hace backfill de
   `matches.source_url` cuando difiere (nuevo contador `urls_updated`).
2. **URL jugador sin season slug** (`302331f`): `/jugadores/{slug}/{season-slug}`
   sigue devolviendo 200 pero sirve una pagina SIN la 2a `tablestats` de stats
   por jornada → `parse_player_stats` daba "sin stats" para todo. Fix: URL
   actualizada a `/jugadores/{slug}` en `scrape_matchday` y
   `scrape_match_players`.
3. **Tabla de stats por indice vs por contenido** (`97514b9`):
   `parse_player_stats` hardcodeaba `tablestats[1]` (la 2a tabla). Algunos
   jugadores no tienen tabla de resumen previa (e.g. Mikautadze) y solo
   tienen 1 `tablestats` → daba None aunque tenian J38 jugada. Fix: buscar
   la primera `table.tablestats` que contenga `td.jorn-td`.
4. **Posicion / match_id historicos sobrescritos** (`3554599`): los 3 flujos
   de scraping sobrescribian `player_stats.position` con `player.position`
   actual y `match_id` con el match del equipo actual del jugador. Eso
   contradice CLAUDE.md regla 9: la position debe ser la de ESA jornada.
   Fix: si la fila ya existe, preservar `position` y `match_id`; solo
   asignar valores nuevos para filas inexistentes.

## Auditoria de fin de temporada (recipe)

Cuando termina una temporada, se puede re-scrapear todo para verificar
puntos. Procedimiento:

```bash
SID=8
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/vpv
sudo mkdir -p "$BACKUP_DIR"
sudo chown postgres:postgres "$BACKUP_DIR"

# 1) Snapshots in-DB (las 4 tablas que el scraping reescribe)
sudo -u postgres psql -d ligavpv <<EOF
CREATE TABLE player_stats_snap_${TS} AS SELECT * FROM player_stats;
CREATE TABLE participant_matchday_scores_snap_${TS} AS SELECT * FROM participant_matchday_scores;
CREATE TABLE lineup_players_snap_${TS} AS SELECT * FROM lineup_players;
CREATE TABLE lineups_snap_${TS} AS SELECT * FROM lineups;
EOF

# 2) Dumps a disco (full + tablas afectadas)
sudo -u postgres pg_dump -Fc -d ligavpv -f "${BACKUP_DIR}/ligavpv_full_${TS}.dump"
sudo -u postgres pg_dump -d ligavpv \
  -t player_stats -t participant_matchday_scores \
  -t lineup_players -t lineups \
  --data-only --column-inserts \
  -f "${BACKUP_DIR}/ligavpv_scoring_${TS}.sql"

# 3) Re-scrape (en background, ~30 min para una temporada completa)
cd /opt/vpv/backend
sudo -u vpv nohup .venv/bin/python -m src.features.scraping.cli scrape-season-full ${SID} \
  --start 6 --end 38 > /tmp/rescrape_full.log 2>&1 &

# 4) Tras terminar, query de deltas
sudo -u postgres psql -d ligavpv <<EOF
SELECT 'pts deltas' AS what, count(*)
FROM player_stats ps
JOIN matchdays md ON md.id = ps.matchday_id
LEFT JOIN player_stats_snap_${TS} o USING (player_id, matchday_id)
WHERE md.season_id = ${SID}
  AND COALESCE(o.pts_total, -9999) <> COALESCE(ps.pts_total, -9999);
EOF
```

Si los deltas son extranos, restore quirurgico (sin TRUNCATE) desde snapshot:
```sql
UPDATE player_stats ps SET position = o.position
FROM player_stats_snap_${TS} o
WHERE ps.player_id = o.player_id AND ps.matchday_id = o.matchday_id
  AND ps.position <> o.position;
-- Idem para match_id.
```

Limpieza de snapshots cuando ya no se necesiten:
```sql
DROP TABLE player_stats_snap_${TS};
DROP TABLE participant_matchday_scores_snap_${TS};
DROP TABLE lineup_players_snap_${TS};
DROP TABLE lineups_snap_${TS};
```
