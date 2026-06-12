# Scraping del Mundial (y otros torneos)

## Contexto

El sistema heredado de Liga scrapea **un fetch por jugador y jornada** a
`https://www.futbolfantasy.com/jugadores/{slug}` y busca la fila de la
jornada N en una tabla con `td.jorn-td`. Para el Mundial el HTML del
jugador NO tiene `td.jorn-td`, así que el parser devolvía `None` en
silencio y los puntos no llegaban a `player_stats`.

Decisión (2026-06-12): en torneos cambiamos la **fuente de datos** del
scrape: en vez de la página del jugador usamos la **página del partido**
(`/partidos/{id}-{home}-{away}`), que ya contiene 52 jugadores con
stats raw en un solo HTML.

## Activación por temporada

La estrategia se selecciona vía `seasons.tournament_config["stats_source"]`:

| Valor | Comportamiento |
|---|---|
| `"player_page"` *(default)* | Flujo histórico de Liga: N fetches por jugador. |
| `"match_page"` | Un fetch por partido, parsea 52 jugadores de golpe. |

Valores desconocidos hacen fallback a `"player_page"` (no rompemos
Liga si alguien escribe mal el config).

Helper en código: [`stats_source_for()`](../backend/src/features/scraping/config.py)
en `backend/src/features/scraping/config.py`.

### Encender para el Mundial en producción

```sql
UPDATE seasons
   SET tournament_config = jsonb_set(
     coalesce(tournament_config, '{}'::jsonb),
     '{stats_source}', '"match_page"'
   )
 WHERE kind = 'tournament'
   AND tournament_type = 'mundial';
```

Si quieres apagarlo:

```sql
UPDATE seasons
   SET tournament_config = tournament_config - 'stats_source'
 WHERE kind = 'tournament'
   AND tournament_type = 'mundial';
```

### El scheduler ya considera torneos

Hasta el 2026-06-12 el scheduler filtraba por `kind='league'` y se
saltaba los torneos (logueaba `"Sin temporada activa, omitiendo"` cada
15 min en pleno Mundial). Ya está corregido: `get_active_season()` mira
cualquier season con `status='active'` y, si hay varias en paralelo,
toma la del `id` más alto (la más reciente).

Implicación operativa: si Liga y Mundial están `active` a la vez (caso
raro — solapamiento septiembre/octubre por temporadas que no han
cambiado de estado), el scheduler sólo procesará una de las dos por
tick. Cambia el `status` de la que no corresponda a `'paused'` o
`'finished'` para que el scheduler trabaje sobre la deseada.

### Verificación manual tras activarlo

```bash
# fuerza re-scrape de una jornada con datos publicados
python -m src.features.scraping.cli scrape-matchday <season_id_mundial> <numero_jornada>
# luego en psql
SELECT player_id, position, pts_total, goals, assists, yellow_card, red_card
  FROM player_stats
  WHERE matchday_id = <id>
  ORDER BY pts_total DESC
  LIMIT 20;
```

Si la lista sale vacía o con todo a 0, mira los logs:

```bash
sudo journalctl -u vpv-backend -f | grep scrape_matchday
```

Las líneas relevantes son las que llevan `[match_page]` en el prefijo.

## Qué se extrae de la página del partido

Punto de entrada: `parse_match_page_players(html, ...)` en
[`parsers.py`](../backend/src/features/scraping/parsers.py).

### Selectores y semántica

| Dato VPV | Cómo lo sacamos del DOM |
|---|---|
| `team_name` | tabla #0 = local, #1 = visitante (orden fijo de `tablestats`). |
| `surname_clean` | última palabra de `td.name`, lowercase, sin diacríticos. Strip de marcas tipo `91'`. |
| `is_starter` | flips a `False` al cruzar la fila `tr.header` con texto "Suplentes". |
| `minutes_played` | titular sin minuto = 90 · titular con `NN'` = NN · suplente con `NN'` = 90−NN · suplente sin minuto = 0. |
| `home_score` / `away_score` | de `.resultado` (formato "México 2 0 Sudáfrica"). |
| `result` (0/1/2) | derivado de goals_for vs goals_against según local/visitante. |
| `as_picas` | **número de `<img class="pica">` dentro de `td.picas`** (icono = 1 pica). |
| `marca_rating` | `td.marca`. "SC" y "-" → `None`. |
| `yellow_card` / `red_card` / `double_yellow` | alt-text de `<img>` en `td.events`: "Amarilla" / "Roja directa". 2 amarillas → double_yellow + red. |
| `own_goals` | alt-text "Error garrafal en gol en contra" en `td.events`. |
| `goals`, `assists`, `woodwork` | desglose row (`tr.desglose`), columna con más estadísticas (usualmente `div.desg.futbolfantasy-rpg`). |

### Limitaciones conocidas (siempre = 0 / False en match_page)

| Campo | Por qué |
|---|---|
| `penalty_goals` | No hay distinción "gol normal" vs "gol de penalti" en el desglose. |
| `penalties_missed` | Sin evento dedicado en la match page. |
| `penalties_won` | Sin evento dedicado. |
| `penalties_committed` | Sin evento dedicado. |
| `penalties_saved` | "Paradas" en el desglose es **total de paradas**, no paradas de penalti. VPV solo puntúa paradas de penalti, así que dejamos el campo en 0 hasta que veamos un caso real para mapear el evento concreto. |
| `yellow_removed` | No publicado en la match page. |

Cuando ocurra alguno en un partido real (p.ej. un penalti parado),
guarda el HTML como fixture nuevo en `tests/fixtures/scraping/` y
añade el mapping al parser + tests.

### "Paradas" ≠ `penalties_saved`

Decisión explícita: aunque el desglose tiene "Paradas → N", **no se
mapea** a `penalties_saved`. VPV solo puntúa las paradas de penalti
(no las paradas normales). Hardcodeamos `penalties_saved = 0` para la
fuente `match_page` hasta que aparezca un caso real con el evento
correcto.

## Matching de jugador (BD ↔ scrape)

La match page no expone `slug` — solo el apellido tal como sale en TV.
Resolvemos por `team_id + surname` con normalización:

```python
def _surname_key(name: str) -> str:
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower().strip()
    return n.split()[-1] if n else ""
```

Caracteres acentuados se aplastan ("Jiménez" → "jimenez", "Gutiérrez"
→ "gutierrez"). Si dos jugadores comparten apellido en el mismo
equipo, el último carga; v1 no maneja desambiguación.

Jugadores que aparecen en la match page pero no en el roster de la BD
se ignoran en silencio (caso típico: suplente que nunca se llamó a la
plantilla del torneo en la BD).

## Coste operacional

| Métrica | player_page (antes) | match_page (ahora) | Reducción |
|---|---|---|---|
| Fetches por jornada | ~52 (26 por equipo × 2) | ~12 (1 por partido) | **~77 %** |
| Latencia esperada | ~80 s con `scraping_delay_min=1` | ~18 s | ~4× más rápido |
| Datos por fetch | 1 jugador | 52 jugadores | 52× densidad |

## Tests

[`tests/features/test_match_page_parser.py`](../backend/tests/features/test_match_page_parser.py)
fija el contrato. 21 tests sobre el fixture
[`match_mundial_mex_sud.html`](../backend/tests/fixtures/scraping/match_mundial_mex_sud.html)
(México 2-0 Sudáfrica, Mundial 2026). Incluyen:

- 52 jugadores, 11 titulares por equipo, 26 por equipo (titulares + suplentes).
- Resultado del partido aplicado a todos (perspective check Mex=win, Sud=loss).
- Minutos inferidos: titular sin marca = 90, titular con marca = N, suplente con marca = 90−N.
- Picas extraídas como conteo de imgs.
- Tarjeta amarilla / roja directa / error en gol en contra detectados de `td.events`.
- Apellido normalizado: "Jiménez" → "jimenez", "Brian Gutiérrez" → "gutierrez", "Montes 91'" → "montes".

Cuando futbolfantasy redibuje la página del partido, estos tests
saltarán; actualiza fixture + parser a la vez.

## Cómo añadir soporte para un torneo nuevo

1. Asegúrate de que el `tournament_type` esté en el mapa
   `_TOURNAMENT_URL_PREFIX` de [`config.py`](../backend/src/features/scraping/config.py)
   (necesario para `competition_url_prefix`).
2. Importa equipos / players / matches normalmente
   (`import_teams_and_players`).
3. Activa la fuente con `UPDATE seasons SET tournament_config = ...
   '{stats_source}', '"match_page"' ...`.
4. Ejecuta `scrape-matchday` y mira logs.

Si la estructura HTML del torneo difiere (otra disposición de tablas,
desglose distinto), añade un fixture nuevo a `tests/fixtures/scraping/`
y un caso de test al detectarlo. El parser está abierto para extender
sin tener que renombrar el config — basta con que el HTML siga las
convenciones de `tablestats / plegado / desglose / desg.{system}`.

## Ficheros clave

| Capa | Fichero | Responsabilidad |
|---|---|---|
| Config | `backend/src/features/scraping/config.py` | `stats_source_for()`, `_TOURNAMENT_URL_PREFIX`. |
| Parser | `backend/src/features/scraping/parsers.py` | `parse_match_page_players()` + dataclass `MatchPagePlayer`. |
| Service | `backend/src/features/scraping/service.py` | `_process_match_via_match_page()`, branch en `scrape_matchday`. |
| Tests | `backend/tests/features/test_match_page_parser.py` | 21 tests sobre fixture. |
| Fixture | `backend/tests/fixtures/scraping/match_mundial_mex_sud.html` | HTML real México-Sudáfrica J1. |
