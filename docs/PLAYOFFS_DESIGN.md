# Playoffs — Diseño (DOCUMENTACIÓN, no implementar ahora)

> Estado: **diseño aprobado en lo conceptual, NO implementar en este turno**.
> Cuando se retome, mover este fichero a `docs/PLAYOFFS_DESIGN.md` del repo
> (es la única acción de "implementación" que se solicita ahora).

## Context

La tabla `competitions` se creó en la migración inicial como placeholder
([backend/src/shared/models/competition.py](backend/src/shared/models/competition.py)) y nunca se cableó a nada.
Queremos darle uso para introducir el concepto de **Playoff** con el formato real
que se ha jugado históricamente:

- **Liga**: 2 Playoffs por temporada — **Apertura** y **Clausura**.
- **Torneo** (Mundial / Eurocopa): 1 Playoff.

El formato **NO es una clasificación acumulada**: es una **liguilla
round-robin** entre participantes VPV donde cada jornada VPV se transforma en
una jornada de cruces directos (Dani C vs Xavi V, 3Cerros vs Hector, etc.).
Tras la fase regular hay **eliminatorias KO** entre el top-N.

## Reglas de Negocio (acordadas)

### Round-robin

- **Calendario**: round-robin completo. Con N participantes (impar) se juegan
  **N jornadas** (cada uno descansa una vez); con N par se juegan **N-1**.
  - Apertura = primera vuelta (las primeras N-1/N jornadas del rango).
  - Clausura = segunda vuelta (las siguientes).
  - Si la temporada empieza tarde (J8, J18, ...) o tiene menos jornadas
    disponibles, el algoritmo se ajusta al rango real.
- **Cruces por jornada**: pre-generados al iniciar el Playoff via algoritmo
  de Berger / round-robin clásico. Determinista a partir de la lista de
  participantes y la jornada inicial.
- **Puntuación de cada cruce**:
  - Victoria = **3 pts** (más puntos VPV en esa jornada).
  - Empate (igualdad de puntos VPV) = **1 pt** a cada uno.
  - Derrota = **0 pts**.
  - **Descanso = 0 pts** para el participante que descansa.
- **Diferencial ("average")**: `pts_VPV(propios) - pts_VPV(rival)` por cruce,
  acumulado, sirve como desempate en la clasificación.
- **Clasificación**: orden por `playoff_points DESC, diff_avg DESC, pts_total_VPV DESC`.

### Eliminatorias

- Tras el round-robin, **top-N** pasa automáticamente (N configurable: 4, 6, 8...).
- **Cruces deterministas** estilo Champions (1º vs Nº, 2º vs N-1º, ...).
- **Tipo configurable por eliminatoria**: partido único o ida-vuelta (decisión
  del admin en función de jornadas disponibles).
  - Partido único: resultado = comparación de 1 jornada.
  - Ida-vuelta: suma de los 2 partidos; en empate, el mejor clasificado del
    round-robin avanza.

### Premios

- Palmarés (ganador del Playoff queda registrado).
- Económico configurable: nuevo `payment_type='playoff_prize'` con
  `position_rank` por puesto (1º obligatorio, 2º/3º opcionales).

---

## Plan de Implementación (cuando se retome)

### Cambios de BD

#### Migración 1 — `season_payments` linkadas a competición

```sql
ALTER TABLE season_payments
  ADD COLUMN IF NOT EXISTS competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE;
ALTER TABLE season_payments DROP CONSTRAINT IF EXISTS uq_season_payment;
ALTER TABLE season_payments ADD CONSTRAINT uq_season_payment
  UNIQUE (season_id, payment_type, position_rank, competition_id);
CREATE INDEX IF NOT EXISTS idx_season_payments_competition
  ON season_payments(competition_id);
```

#### Migración 2 — calendario de cruces

```sql
CREATE TABLE IF NOT EXISTS competition_matchups (
  id              SERIAL PRIMARY KEY,
  competition_id  INT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  phase           VARCHAR(20) NOT NULL,            -- 'round_robin' | 'ko'
  round_number    SMALLINT NOT NULL,
  matchday_id     INT REFERENCES matchdays(id),    -- jornada VPV donde se juega
  -- round-robin
  participant_a_id INT REFERENCES season_participants(id),
  participant_b_id INT REFERENCES season_participants(id),
  rest_participant_id INT REFERENCES season_participants(id),
  -- ko (puede llenarse en 2 leg: matchday + leg)
  leg              SMALLINT DEFAULT 1,             -- 1 o 2 (ida/vuelta)
  feeder_a_id     INT REFERENCES competition_matchups(id),
  feeder_b_id     INT REFERENCES competition_matchups(id),
  -- resultado
  score_a         INT,
  score_b         INT,
  winner_participant_id INT REFERENCES season_participants(id),
  UNIQUE (competition_id, phase, round_number, leg, matchday_id, participant_a_id),
  CHECK (participant_a_id <> participant_b_id)
);
CREATE INDEX idx_matchups_competition ON competition_matchups(competition_id);
CREATE INDEX idx_matchups_matchday    ON competition_matchups(matchday_id);
```

### Modelo SQLAlchemy

- `backend/src/shared/models/season.py::SeasonPayment` → añadir `competition_id`.
- `backend/src/shared/models/competition.py` → añadir relación `matchups`.
- Nuevo `backend/src/shared/models/competition_matchup.py`.

### Backend — módulo nuevo `features/competitions/`

- `service.py`:
  - `ensure_playoffs(season_id)` — al setear `matchday_winter` (Liga) o al
    finalizar fase de grupos (Mundial), crea las 1-2 competitions vacías.
  - `start_playoff(competition_id, participant_ids)` — genera el round-robin
    completo via algoritmo de Berger. Inserta filas `competition_matchups`
    con `matchday_id` asignada secuencialmente. Idempotente con guard.
  - `recalculate_matchup(matchup_id)` — lee `participant_matchday_scores`
    para los 2 participantes en su `matchday_id`, asigna `score_a/score_b`
    y `winner_participant_id`. Llamado desde el aggregator del scraping.
  - `get_standings(competition_id)` — agrega:
    - `playoff_points` por participante (3/1/0).
    - `diff_avg` (suma de diferencias VPV).
    - `pts_total_VPV` (desempate último).
  - `start_ko_phase(competition_id, top_n)` — toma los top-N del
    round-robin, genera bracket KO determinista. Acepta `legs_per_round`
    (`[1,1,2,2]` etc).
- `router.py`:
  - `GET /competitions/{season_id}` (público).
  - `GET /competitions/{id}/standings` (público).
  - `GET /competitions/{id}/matchups` (público, calendario).
  - `POST /competitions/admin/{id}/start-round-robin` (admin).
  - `POST /competitions/admin/{id}/start-ko` (admin, body: `top_n`, `legs`).
  - `POST /competitions/admin/{id}/finalize` (admin).

### Wiring con scraping/scoring

`scraping/aggregation.py::aggregate_matchday` — tras recalcular
`participant_matchday_scores` para una jornada, llamar al servicio para que
recalcule todos los `competition_matchups` con esa `matchday_id`. El cambio
es idempotente (puede correr varias veces).

### Frontend

- `/admin/temporadas` → nueva tarjeta **"Playoffs"** (visible para Liga y
  Tournament):
  - Apertura / Clausura (Liga) o Playoff único (Tournament).
  - Botón "Generar round-robin" cuando todavía no se generó.
  - Premio 1º/2º/3º editables.
  - Botón "Iniciar eliminatorias" con `top_n` y `legs` configurables.
  - Botón "Finalizar" cuando todos los matchups estén resueltos.
- `/playoffs` — página pública:
  - Tabs por competición (Apertura | Clausura | Playoff).
  - Sub-tabs: **Calendario** (matchups por jornada) | **Clasificación** | **Eliminatorias** (bracket).
- `/palmares` — añadir sección "Ganadores Playoff".
- `sidebar.tsx` → entrada `/playoffs` per-season (kind=tournament o kind=league con `playoffs_enabled`).

### Componentes UI reusables

- Para el bracket KO entre participantes, reusar componentes de
  `frontend/src/app/bracket/page.tsx` (`CompactMatchCard`, `TwoSidedBracket`)
  sustituyendo `CountryFlag` por avatar de participante y `team.name` por
  `participant.display_name`.

### Algoritmo de Berger (round-robin)

Pseudocódigo:
```
participants = lista ordenada
if len(participants) impar:
    participants.append(BYE)
n = len(participants)
fixed = participants[0]
rotating = participants[1:]
for round in 1..n-1:
    pairs = [(fixed, rotating[-1])]
    for i in 0..n/2-2:
        pairs.append((rotating[i], rotating[-2-i]))
    rotating = [rotating[-1]] + rotating[:-1]
    # 'pairs' = cruces de esta jornada; uno puede tener BYE -> rest
```

### Premio: `payment_type='playoff_prize'`

- Validación en `seasons/service.py::upsert_payment`:
  - `competition_id` obligatorio.
  - `position_rank in {1, 2, 3}`.
- Generación de transactions: `economy/service.py::generate_playoff_prizes(competition_id)`
  - Idempotente (delete + recreate).
  - Llamado desde `finalize`.

### Verificación E2E

1. Migraciones aplicadas; `\d competition_matchups` muestra columnas correctas.
2. Crear Competition manual via SQL, llamar `start_playoff` con 13
   participantes; comprobar que se generan 13 jornadas × 6 cruces + 1
   descanso = 91 filas en `competition_matchups`.
3. Comprobar que el `matchday_id` asignado es secuencial dentro del rango
   `config.matchday_start..config.matchday_end`.
4. Recalcular un matchup tras un scraping → verificar que `winner_participant_id`
   coincide con el participante con más puntos VPV en esa jornada.
5. UI admin: generar round-robin → ver calendario en `/playoffs/calendario`.
6. Iniciar KO con `top_n=4, legs=[1,2]` → verificar bracket generado.
7. Finalize → transaction de premio creada y reflejada en `/economia`.

### Ficheros críticos

| Capa | Fichero | Acción |
|---|---|---|
| Migración | `migration/schema/migrations/2026_..._add_competition_id_to_payments.sql` | nuevo |
| Migración | `migration/schema/migrations/2026_..._add_competition_matchups.sql` | nuevo |
| Modelo | `backend/src/shared/models/season.py` | `SeasonPayment.competition_id` |
| Modelo | `backend/src/shared/models/competition.py` | relación `matchups` |
| Modelo | `backend/src/shared/models/competition_matchup.py` | nuevo |
| Servicio | `backend/src/features/seasons/service.py` | `playoff_prize` + trigger `ensure_playoffs` |
| Servicio | `backend/src/features/economy/service.py` | `generate_playoff_prizes` |
| Nuevo | `backend/src/features/competitions/{schemas,repository,service,router}.py` | módulo completo |
| Servicio | `backend/src/features/scraping/aggregation.py` | recálculo de matchups tras agregar jornada |
| Router | `backend/src/app.py` | registrar `competitions.router` |
| Frontend | `frontend/src/app/admin/temporadas/page.tsx` | tarjeta Playoffs |
| Frontend | `frontend/src/app/playoffs/page.tsx` | nuevo |
| Frontend | `frontend/src/components/layout/sidebar.tsx` | entrada `/playoffs` |
| Frontend | `frontend/src/app/palmares/page.tsx` | sección playoffs |

### Decisiones que quedan abiertas (pendientes para la retoma)

1. **Sorteo de orden de participantes**: ¿lo decide el admin (drag&drop como
   en draft order) o se hereda de `season_participants.draft_order`?
2. **Recálculo retroactivo**: al cambiar `matches.counts` o `matchdays.counts`,
   ¿qué hacer con matchups ya resueltos? Probablemente: recalcular y avisar.
3. **Descanso justo**: el algoritmo de Berger garantiza rotación, pero con
   N impar siempre hay alguien que descansa. ¿Se acepta como tal o se busca
   compensación (p.ej. doblar puntos en otra jornada)? Acordado: no
   compensar — descanso = 0 pts.
4. **Coexistencia Liga + Mundial**: si una season tiene un Mundial paralelo,
   ¿el Playoff del Mundial es una competition separada en una season Tournament
   distinta? Sí — cada season tiene sus propias competitions.

---

## Próxima acción sugerida

Cuando se retome este tema:
1. Mover este fichero a `docs/PLAYOFFS_DESIGN.md` del repo.
2. Confirmar las "decisiones abiertas" con un AskUserQuestion.
3. Implementar en el orden: migraciones → módulo backend → wiring scraping → admin UI → /playoffs pública → palmarés.
