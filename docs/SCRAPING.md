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
  router.py           # 8 endpoints FastAPI
```

### Configuracion (`config.py`)

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `SCRAPING_BASE_URL` | `https://www.futbolfantasy.com` | URL base de futbolfantasy |
| `SCRAPING_SEASON_SLUG` | `laliga-25-26` | Slug temporada para URLs de jugadores |
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

# Actualizar calendario (resultados + fechas)
python -m src.features.scraping.cli update-calendar 8

# Verificar cambios en homepage (CRC)
python -m src.features.scraping.cli check-updates

# Descargar fotos de jugadores
python -m src.features.scraping.cli download-photos 8
```

## Flujo de datos completo

### Inicio de temporada

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
| `futbolfantasy.com/jugadores/{slug}/{season_slug}` | Stats jugador por jornada | `parse_player_stats` |
| `futbolfantasy.com/partidos/{id}-{slug}` | Pagina partido — CRC ratings | `parse_match_crc` |
| `futbolfantasy.com/{team-slug}` | Plantilla equipo | `parse_roster` |

## Deteccion de cambios (CRC)

Dos niveles de CRC:

1. **Homepage CRC** (legacy, deprecated): CRC de toda la seccion de jornada actual. Poco fiable — cambia por cualquier razon.

2. **Per-match CRC** (actual): Para cada partido jugado, calcula CRC de los ratings `modo-picas` + `cronistas-marca` de la pagina del partido. Solo dispara re-scrape cuando los ratings de ese partido especifico cambian. Almacenado en `matches.stats_crc`.

## Notas importantes

- **Rate limiting**: Delay aleatorio 1-4s entre requests. El sistema scrapea ~40-50 jugadores por partido (2 equipos x ~25 jugadores). Una jornada completa (10 partidos) puede tardar 30-60 minutos.
- **Idempotencia**: `upsert_player_stat` usa `ON CONFLICT (player_id, matchday_id)` — re-scrapear es seguro.
- **Posicion**: `player_stats.position` es la fuente de verdad para puntos, no `players.position` (un jugador puede cambiar de posicion entre jornadas).
- **Counts a 2 niveles**: `matchdays.counts` Y `matches.counts` determinan si un partido/jornada computa para la clasificacion. El scraping procesa todos los matches con `counts=True`.
- **Fechas del calendario**: Solo los partidos pendientes tienen fecha en el HTML. Los ya jugados no muestran fecha, solo resultado. Las fechas ya almacenadas en BD para partidos jugados son las originales de la migracion.
