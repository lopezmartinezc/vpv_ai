# Draft live — mejoras planificadas para septiembre 2026

> Estado: **plan aprobado, NO implementado**. Para retomar en septiembre cuando
> arranque la nueva temporada de Liga. El draft del Mundial 2026 ya cerró con
> el sistema actual (sin estas mejoras) — funcionó pero hubo fricción.

## Context

La página `/drafts/live/{id}` actualmente carga **un** endpoint de stats con un
modelo simple. Existe un sistema mucho más sofisticado y backtested
([service_draft.py](backend/src/features/stats/service_draft.py), Spearman 0.718)
pero **no está conectado al draft live**. El admin tiene que abrir
`/admin/estadisticas` en otra pestaña y cruzar la información a ojo.

> **Input crítico**: [DRAFT_SCORECARD.md](DRAFT_SCORECARD.md) contiene el
> análisis de qué métricas valen por posición y los overrides (regresión,
> haircut de supervivencia, ajuste por cambio de equipo). El UI debe traducir
> esos tiers a badges y los haircuts a ajustes del `ensemble_score` antes de
> mostrar sugerencias.

Tres mejoras que confirmadas para septiembre:

1. **Conectar el modelo Ensemble al draft live**: badge de señal en cada card,
   sugerencias por posición usando el modelo backtested.
2. **Comparativa lateral de 2-3 jugadores**: panel con métricas lado a lado.
3. **Tracker de "valor que se ha ido"**: por cada pick mostrar el
   `ensemble_score` capturado y running total por participante.

## Mejora 1 — Conectar el modelo Ensemble al draft live

### Estado (2026-06-09): COMPLETADA + Scorecard heurístico aplicado

Cerrada antes de septiembre con un alcance ampliado para incorporar las
6 implicaciones técnicas del análisis externo
([docs/DRAFT_SCORECARD.md](DRAFT_SCORECARD.md)).

**Backend entregado**:
- [backend/src/features/stats/scorecard.py](../backend/src/features/stats/scorecard.py)
  — módulo puro con `tier_for`, `survival_haircut`, `is_peak_year`,
  `is_mover`, `is_likely_penalty_taker`, `enrich`.
- `DraftValueService` ya devuelve `ensemble_score` + `signal` + razones;
  `get_player_stats_for_draft` lo envuelve y aplica `enrich` por jugador.
- `_PlayerSeason` ahora separa `penalty_goals` / `penalties_missed`
  del agregado `goals` para detectar lanzadores.
- `DraftValuePlayer.slug` añadido para join estable entre temporadas
  (el `player_id` cambia, el slug no).
- Suggestions se ordenan por `effective_score` (ensemble × (1 − haircut)),
  no por la fórmula heurística antigua.

**Frontend entregado** ([drafts/live/[draftId]/page.tsx](../frontend/src/app/drafts/live/%5BdraftId%5D/page.tsx)):
- Tier badge (elite/sólido/normal/flojo) por jugador.
- Signal badge (⭐ STRONG BUY / 🟢 BUY / 🔵 HOLD / 🔴 AVOID) con tooltip
  mostrando `signal_reasons`.
- Flags 🔄 (mover) / 🔻 (peak año) / ⚽ (penaltis).
- `xPts` efectivo en bold accent + métricas de soporte (avg / PJ / T%).
- Panel "Sugerencias" ordenado por effective_score con los mismos flags.
- Todo el bloque sigue gated por `isAdmin && adminStats`.

**Tests**: [backend/tests/features/test_scorecard.py](../backend/tests/features/test_scorecard.py)
cubre thresholds por posición + brackets de haircut + flags + enrich
end-to-end (24 tests verdes).

### Estado previo (referencia histórica)

[backend/src/features/drafts/service.py:890](../backend/src/features/drafts/service.py#L890)
`get_player_stats_for_draft` calculaba localmente:
- `avg_pts × starter_factor × trend_factor` para el ranking.
- Devolvía `PlayerDraftStats` (avg/std/form/trend/matchdays/starter_pct).

El frontend lo mostraba inline en las cards de búsqueda + panel
"Sugerencias de pick (Admin)".

### Cambios

#### Backend

- **Reemplazar `get_player_stats_for_draft`** para que delegue en
  `DraftValueService.get_draft_value(season_id, draft_type)` que ya existe y
  devuelve `DraftValueResponse` con `ensemble_score`, `signal`,
  `signal_reasons`, etc.
- Filtrar la respuesta a los jugadores aún disponibles (no pickeados +
  `is_available=True`).
- Recortar la respuesta a sólo los campos que la UI del draft live necesita
  (no mandar las 15+ métricas si no las vamos a mostrar todas).
- Mantener el endpoint actual `GET /drafts/{id}/players/stats` para
  retrocompatibilidad — pero el response model evoluciona.

Schema nuevo (sustituye `DraftPlayerStatsResponse`):

```python
class DraftLivePlayerStats(BaseModel):
    player_id: int
    # Modelo
    ensemble_score: float       # 0..N — más alto = mejor pick
    signal: str                 # "strong_buy" | "buy" | "hold" | "avoid"
    signal_reasons: list[str]   # razones humanas
    # Métricas mostradas en card
    avg_points: float
    second_half_avg: float | None
    availability: float         # 0..1
    consistency: float          # 0..1
    career_trend_pct: float | None
    # Helpers para la UI
    matchdays_played: int
    starter_pct: float
    games_played: int

class DraftLiveStatsResponse(BaseModel):
    season_id: int
    draft_type: str             # 'preseason' | 'winter'
    matchdays_played: int       # del draft-value endpoint
    model_info: dict[str, str]  # nombres legibles
    players: dict[str, DraftLivePlayerStats]
    suggestions: dict[str, list[int]]  # por posición top-N
```

`suggestions` ahora se ordena por `ensemble_score` directo (no por la fórmula
manual actual).

#### Frontend

`frontend/src/app/drafts/live/[draftId]/page.tsx`:

- Card de jugador en resultados de búsqueda:
  - Añadir **badge de señal** a la derecha de la posición: `🟢 BUY`, `🔵 HOLD`,
    `🔴 AVOID`, `⭐ STRONG BUY`.
  - Tooltip al pasar el ratón con `signal_reasons` ("Ensemble top 15% · Trending
    +18% · Availability 92%").
  - Reemplazar `pts/j` por `xPts` (ensemble_score) en negrita.
- Panel "Sugerencias" (existente):
  - Top-N por posición ordenado por `ensemble_score`.
  - Mostrar el badge de señal en cada sugerencia.
  - Botón "Pickear este" al lado de cada sugerencia (ya existe en parte).

### Ficheros tocados

| Capa | Fichero | Acción |
|---|---|---|
| Backend | `backend/src/features/drafts/service.py` | Reescribir `get_player_stats_for_draft` |
| Backend | `backend/src/features/drafts/schemas.py` | Nuevos `DraftLivePlayerStats` + `DraftLiveStatsResponse` |
| Backend | `backend/src/features/stats/service_draft.py` | Añadir método `for_unpicked_players(draft_id)` que filtra (probablemente más eficiente que llamar al endpoint público) |
| Frontend | `frontend/src/types/index.ts` | Nuevos tipos |
| Frontend | `frontend/src/app/drafts/live/[draftId]/page.tsx` | Render del badge + tooltip |

---

## Mejora 1.5 — Draft Retro analytics (entregada 2026-06-09)

Tras cerrar la Mejora 1 quedaba la pregunta "¿hubiera funcionado el
scorecard?". Esta mejora añade una capa retrospectiva con cuatro vistas
admin sobre `draft_picks` + `player_stats`:

1. **Retrospectiva por draft** — `GET /stats/admin/drafts/{draft_id}/retrospective`
   Tabla pick-a-pick con `season_total_points`, `slot_median_total_points`
   (mediana histórica del mismo `pick_number`), `delta_vs_slot` y tag
   `steal`/`bust`/`normal` por cuartiles dentro del draft.

2. **Scatter histórico** — `GET /stats/admin/drafts/scatter`
   Cada pick como punto en un ScatterChart de recharts (primer scatter
   del repo). Color por posición, línea amarilla = mediana del slot.
   Outliers arriba = steals, abajo = busts.

3. **Backtest del scorecard** — `GET /stats/admin/drafts/backtest?season_id=X`
   Reentrena con seasons < X, aplica `scorecard.enrich()`, compara con
   los puntos reales de la season X. Devuelve Spearman ρ + médias por
   signal/tier. Sanity check: el grupo `strong_buy` debe puntuar más
   que `avoid`.

4. **Draft IQ** — `GET /stats/admin/drafts/participant-iq`
   Ranking de participantes por `mean_delta_per_pick` con mejor/peor
   pick histórico y breakdown por ronda (¿quién acierta en R1 vs R10?).

| Capa | Fichero | Acción |
|---|---|---|
| Backend | `backend/src/features/stats/service_draft_retro.py` | NUEVO — lógica + SQL |
| Backend | `backend/src/features/stats/schemas_draft_retro.py` | NUEVO — Pydantic |
| Backend | `backend/src/features/stats/router.py` | +4 endpoints `/admin/drafts/...` |
| Tests | `backend/tests/features/test_draft_retro.py` | NUEVO — pure helpers (20 tests) |
| Frontend | `frontend/src/components/admin/draft-retro-tab.tsx` | NUEVO — tab + 4 sub-vistas |
| Frontend | `frontend/src/lib/draft-scorecard.ts` | NUEVO — constantes compartidas |
| Frontend | `frontend/src/app/admin/estadisticas/page.tsx` | +tab "Draft Retro" |
| Frontend | `frontend/src/app/drafts/live/[draftId]/page.tsx` | refactor: importa desde lib/ |

Decisiones cerradas:
- `tag_pick` usa cuartiles inclusivos dentro del propio draft (no umbral
  fijo) — comparativo, no absoluto.
- El backtest usa una ensemble simplificada (mean(last, career)) en
  lugar de la productiva, para aislar el efecto del scorecard.
- Las medianas del slot baseline se calculan con todas las temporadas
  válidas en la misma fase; no se segmenta por posición porque el slot
  ya captura escasez implícitamente.

---

## Mejora 1.6 — Refinamientos del scorecard (entregada 2026-06-09)

Tras un nuevo análisis (Claude Fable, junio 2026), refinamos cuatro
piezas concretas del scorecard porque la versión inicial perdía señal
en casos importantes:

1. **POR sin tiers**. El rango p25–p90 de avg_pts en porteros (5.4–7.6)
   es demasiado estrecho para que los tiers signifiquen algo. Ahora
   `tier_for("POR", ...)` devuelve `"team_dependent"` con label
   "Evalúa equipo". El admin sabe que tiene que mirar la calidad
   defensiva del club, no el número del portero.

2. **Flag 📌 suplente**. Paso 0 del decision-tree: la disponibilidad
   bate al talento. Si `starter_pct < 0.79` o `games_played < 22`
   (p50 del dataset 6-8), el jugador se marca como riesgo de
   banquillo. La banderita sale ANTES de las otras tres en la card.

3. **Mover cuantificado (informativo)**. Cuando `is_mover=True`,
   `mover_penalty_hint` indica magnitud sugerida: POR 2.0 pts, otros
   1.0. El backend NO lo resta automáticamente al `effective_score`
   porque no tenemos la standings del equipo previo; el tooltip lo
   muestra para que el admin lo aplique a mano cuando el salto es
   grande.

4. **Penalti taker matizado**. El flag ⚽ ya marcaba DEL con ≥2
   intentos previos. Añadido al tooltip: "el rol solo persiste el 44%
   YoY — verifica quién lanza esta temporada".

5. **Decision-tree en la leyenda**. Bloque destacado al inicio del
   panel "¿Cómo leo los scores?" que recuerda el orden canónico:
   disponibilidad → tier → entorno → desempate posicional.

### Ficheros tocados

| Capa | Fichero | Acción |
|---|---|---|
| Backend | `backend/src/features/stats/scorecard.py` | `tier_for("POR")="team_dependent"`, `is_bench_risk`, `mover_penalty_hint_for`, `enrich(...starter_pct, games_played)` |
| Backend | `backend/src/features/drafts/schemas.py` | `PlayerDraftStats.is_bench_risk`, `mover_penalty_hint` |
| Backend | `backend/src/features/drafts/service.py` | pasa `starter_pct` + `games` a `enrich` |
| Tests | `backend/tests/features/test_scorecard.py` | 9 tests nuevos: POR tier, bench risk, mover hints; total 33 |
| Frontend | `frontend/src/lib/draft-scorecard.ts` | TIER `team_dependent` color + label |
| Frontend | `frontend/src/types/index.ts` | `is_bench_risk`, `mover_penalty_hint` |
| Frontend | `frontend/src/app/drafts/live/[draftId]/page.tsx` | flag 📌, tooltip penalty, decision-tree block, leyenda POR |

### Pendiente (out-of-scope hoy)

- **xG/xA por jugador** desde Understat para DEL — necesita scraping.
- **Edad del jugador** — necesita columna nueva o scraping.
- **Aplicar `mover_penalty_hint` al `effective_score`** automáticamente
  — requiere tabla de standings por equipo+temporada para gauge del
  salto. Si lo añadimos, queda el efecto cuantitativo en el ranking.

---

## Mejora 2 — Comparativa lateral de 2-3 jugadores

### UX

- Cada card de jugador en los resultados de búsqueda tiene un icono "📌"
  (chincheta) en la esquina superior derecha.
- Click en la chincheta → el jugador entra en una **shortlist** del admin
  (máx 3, FIFO si supera).
- La shortlist aparece como **panel sticky** en la parte derecha (o arriba en
  móvil) con las métricas lado a lado:
  - Tabla horizontal: filas = métricas (avg, ensemble, señal, etc), columnas =
    jugadores.
  - Diferencias resaltadas en verde/rojo cuando hay un ganador claro.
- Botón "Pickear a éste" al lado de cada columna → ejecuta `handlePick`.
- Botón "X" para quitar de la shortlist.

### Estado en frontend

- `useState<SquadPlayerEntry[]>` con la shortlist (máx 3).
- Local al draft live (no se persiste — es contexto efímero del momento del
  pick).
- Reseteo automático cuando el turno cambia al admin (opcional).

### Ficheros tocados

| Capa | Fichero | Acción |
|---|---|---|
| Frontend | `frontend/src/components/draft/shortlist-panel.tsx` | Nuevo |
| Frontend | `frontend/src/app/drafts/live/[draftId]/page.tsx` | Pin icon + shortlist state + render del panel |

Sin cambios backend — todos los datos ya están en el response de la mejora 1.

---

## Mejora 3 — Tracker de "valor que se ha ido"

### Concepto

Cada vez que se hace un pick, el `ensemble_score` del jugador pickeado se
acumula en un running total por participante. El admin (y opcionalmente todos)
ve quién está "capturando más valor" según el modelo.

### Estado actual

Los picks se almacenan en `draft_picks` con `pick_number`, `participant_id`,
`player_id`. NO se guarda el `ensemble_score` en el momento del pick.

### Decisión

Hay dos formas de implementarlo:

**A) Almacenar `ensemble_score` en `draft_picks`** (un score por pick,
inmutable).

- Pro: snapshot real del momento del pick. Sólo se calcula 1 vez.
- Contra: añade columna a tabla draft_picks, migración.

**B) Recalcular en cada render del tracker** (en runtime).

- Pro: sin migración. Si afinas el modelo entre pick y display, refleja la
  versión más reciente.
- Contra: la stats endpoint hay que llamarla en cada refresh; el score
  evoluciona si los datos cambian (no debería pero…).

**Recomendación: A**. El valor del modelo en el momento del pick es lo que
realmente cuenta — fija la decisión histórica.

### Cambios

#### Migración

```sql
-- 2026_09_..._add_draft_pick_value.sql
ALTER TABLE draft_picks
    ADD COLUMN IF NOT EXISTS ensemble_score_at_pick NUMERIC(6, 2);
```

#### Backend

- `DraftService.add_pick`: tras commit del pick, hacer **best-effort** al draft
  value service para conseguir el `ensemble_score` del player y actualizar la
  fila. Si falla, deja `NULL` (no es bloqueante).
- Nuevo endpoint `GET /drafts/{id}/value-tracker` (público):
  ```json
  {
    "participants": [
      {
        "participant_id": 12,
        "display_name": "Hector",
        "picks_count": 4,
        "total_ensemble_score": 87.5,
        "avg_ensemble_score": 21.9
      },
      ...
    ]
  }
  ```

#### Frontend

- Panel "Valor capturado" colapsable en `/drafts/live`, junto a "Participantes":
  - Tabla: posición · participante · picks · score total · score medio.
  - Highlight del líder.
- Update en cada `pick_added` (incremental: añadir score del pick al total del
  participante).

### Ficheros tocados

| Capa | Fichero | Acción |
|---|---|---|
| Migración | `migration/schema/migrations/2026_09_..._add_draft_pick_value.sql` | Nuevo |
| Modelo | `backend/src/shared/models/draft.py` | Añadir `ensemble_score_at_pick` a `DraftPick` |
| Backend | `backend/src/features/drafts/service.py` | Stamp del score en add_pick |
| Backend | `backend/src/features/drafts/router.py` | Endpoint `/value-tracker` |
| Frontend | `frontend/src/components/draft/value-tracker.tsx` | Nuevo |
| Frontend | `frontend/src/app/drafts/live/[draftId]/page.tsx` | Render del panel |
| Frontend | `frontend/src/types/index.ts` | Tipos |

---

## Orden recomendado de implementación

1. **Mejora 1** (Ensemble integrado). Pre-requisito para 2 y 3. Sin esto el
   resto no tiene sentido.
2. **Mejora 3** (Tracker de valor). Reusa el score que ya estamos calculando.
   Implementar antes que la comparativa porque toca BBDD.
3. **Mejora 2** (Comparativa lateral). Puramente frontend. Implementar al
   final, es la más cosmética.

Verificación end-to-end al final:
- Backtest contra el draft del Mundial 2026 (datos reales recién terminados):
  ¿el modelo Ensemble habría sugerido picks similares a los que se hicieron?
  Pueden quedar discrepancias instructivas para enseñar al usuario qué le
  recomienda el modelo cuando él va por otra vía.

## Riesgos / preguntas abiertas para septiembre

- **El modelo Ensemble fue backtested con seasons 5-8** (`VALID_SEASON_IDS = [5, 6, 7, 8]`).
  Para la Liga de septiembre, ¿se reentrena con seasons 5-9? Mirar
  `backend/scripts/draft_backtest.py`.
- **Draft de invierno** (matchday_winter): hay un modelo W1 con Spearman 0.926
  específico para draft parcial. Verificar que `service_draft.py` lo expone
  cuando llamamos con `draft_type='winter'`.
- **Permisos**: ¿el tracker de valor se muestra a todos los participantes o
  sólo al admin? El admin debe poder ocultarlo durante el draft para no
  influir en decisiones ajenas. **Default propuesto: sólo admin**.
