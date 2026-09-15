# Playoffs — API reference

Endpoints del módulo `features/competitions`. Prefijo: `/api/competitions`.

- Uso operativo paso a paso: [PLAYOFFS_RUNBOOK.md](PLAYOFFS_RUNBOOK.md).
- Reglas y estado: [PLAYOFFS_DESIGN.md](PLAYOFFS_DESIGN.md).
- Cómo añadir un formato: [PLAYOFFS_DEV_GUIDE.md](PLAYOFFS_DEV_GUIDE.md).

**Errores.** Todos devuelven `{"code": "...", "message": "..."}`:

| Error | Código |
|---|---|
| Error de negocio | `422` |
| No encontrado | `404` |
| Sin token o token inválido | `401` |
| El usuario no es admin | `403` |

---

## Discovery

### `GET /api/competitions/formats?season_id={id}`

Lista los formatos de playoff disponibles. La tarjeta del admin lo usa para el desplegable y para calcular las jornadas.

**Auth:** ninguna (público).

**`season_id`** es opcional, pero conviene pasarlo:
- En los formatos de todos contra todos, el número de jornadas de liga depende de cuántos participan: `N` si es impar (cada jornada descansa uno) y `N-1` si es par.
- Con `season_id` se cuentan los participantes activos de esa temporada.
- Sin él se asumen 13. Con los 11 de la Liga 2026-27 saldrían 13 jornadas, y `start-regular` rechazaría el calendario.

**Respuesta `200`** (temporada con 11 participantes):

```json
[
  { "format_id": "balanced_ko4", "display_name": "Balanced (4 partidos/uno) + KO top-4",
    "n_rounds_regular": 6, "n_rounds_ko": 2 },
  { "format_id": "liga_berger_ko8", "display_name": "Liga round-robin completo + KO top-8",
    "n_rounds_regular": 11, "n_rounds_ko": 3 },
  { "format_id": "liga_berger_ko8_bo3",
    "display_name": "Liga todos contra todos + KO top-8, final al mejor de 3",
    "n_rounds_regular": 11, "n_rounds_ko": 5 }
]
```

---

## Lecturas (públicas)

### `GET /api/competitions/season/{season_id}`

Competiciones de una temporada. La Liga tiene dos playoffs, distinguidos por `name` (`Apertura` y `Clausura`); un torneo tiene uno.

**Respuesta `200`:**

```json
{
  "season_id": 12,
  "competitions": [
    { "id": 21, "season_id": 12, "name": "Apertura", "type": "playoff", "status": "regular" },
    { "id": 22, "season_id": 12, "name": "Clausura", "type": "playoff", "status": "pending" }
  ]
}
```

**`status`:**
- `pending`: creado, sin calendario;
- `regular`: fase de liga;
- `ko`: eliminatorias;
- `completed`: hay campeón.

---

### `GET /api/competitions/{competition_id}/matchups`

Todos los cruces con los nombres ya resueltos y, en los formatos cuya final dura varias jornadas, la final como serie.

**Respuesta `200`** (extracto de una Apertura en la final):

```json
{
  "competition": {
    "id": 21, "season_id": 12, "name": "Apertura", "type": "playoff", "status": "ko",
    "config": {
      "format_id": "liga_berger_ko8_bo3",
      "seed": 1738291847,
      "matchday_range_regular": { "start": 6, "end": 16 },
      "planned_ko_matchday_numbers": [17, 18, 19, 20, 21],
      "matchday_range_ko": [17, 18, 19, 20, 21],
      "regular_standings_snapshot": [ { "rank": 1, "participant_id": 7, "...": "..." } ]
    }
  },
  "matchups": [
    {
      "id": 301, "phase": "regular", "group_label": "overall", "round_label": null,
      "round_number": 1, "matchday_id": 50, "matchday_number": 6,
      "participant_a_id": 1, "participant_a_name": "Toni",
      "participant_b_id": 5, "participant_b_name": "Dani C",
      "feeder_a_id": null, "feeder_b_id": null,
      "score_a": 75, "score_b": 70, "winner_participant_id": 1, "winner_name": "Toni"
    },
    {
      "id": 362, "phase": "ko", "group_label": null, "round_label": "final",
      "round_number": 15, "matchday_id": 64, "matchday_number": 20,
      "participant_a_id": 7, "participant_a_name": "3Cerros",
      "participant_b_id": 1, "participant_b_name": "Toni",
      "feeder_a_id": 359, "feeder_b_id": 360,
      "score_a": 45, "score_b": 45, "winner_participant_id": null, "winner_name": null
    }
  ],
  "final_series": {
    "participant_a_id": 7, "participant_a_name": "3Cerros",
    "participant_b_id": 1, "participant_b_name": "Toni",
    "wins_a": 1, "wins_b": 0,
    "winner_participant_id": null, "winner_name": null,
    "legs": [
      { "matchup_id": 361, "matchday_number": 19, "score_a": 60, "score_b": 50,
        "result": "a", "decided_by": "points" },
      { "matchup_id": 362, "matchday_number": 20, "score_a": 45, "score_b": 45,
        "result": "pending", "decided_by": null },
      { "matchup_id": 363, "matchday_number": 21, "score_a": null, "score_b": null,
        "result": "pending", "decided_by": null }
    ]
  }
}
```

**Cruces de eliminatoria:**
- `round_label` vale `quarter`, `semi` o `final`.
- `feeder_a_id` / `feeder_b_id` apuntan al cruce cuyo ganador ocupará ese lado.
- En `liga_berger_ko8_bo3`, la final son **tres filas** con `round_label="final"`, una por jornada y todas alimentadas por las dos semis. El ganador de cada semi se escribe a la vez en las tres.

**`final_series`** es `null` en los formatos con final de una jornada y antes de que existan los cruces de la final. Se calcula en cada lectura a partir de los cruces:
- **`result` de cada jornada:**
  - `a` o `b`: la ganó ese lado;
  - `pending`: sin puntuar, o empatada y a la espera de las otras jornadas;
  - `not_needed`: no se disputa, porque alguien ya ganó las dos primeras.
- **`decided_by`:**
  - `points`: la ganó ese día;
  - `difference`: acabó en empate y la decidió la diferencia en las otras dos jornadas de la final;
  - `seed`: también hubo igualdad ahí y la decidió el mejor clasificado de la liga.
- **Ganador de una jornada empatada:** su fila guarda `winner_participant_id = null`; quién la gana lo dice `final_series`.

---

### `GET /api/competitions/{competition_id}/standings`

Clasificación de la fase de liga, calculada en cada lectura desde los cruces resueltos. No se guarda.

**Respuesta `200`:**

```json
{
  "competition": { "...": "..." },
  "groups": [
    {
      "label": "overall",
      "entries": [
        {
          "rank": 1, "participant_id": 7, "display_name": "3Cerros", "group_label": "overall",
          "played": 4, "wins": 4, "draws": 0, "losses": 0, "rests": 1,
          "points": 12, "diff_avg": 65, "pts_total_vpv": 365
        }
      ]
    }
  ]
}
```

**Orden:** `points DESC` y, a igualdad de puntos, depende del formato:

- **`liga_berger_ko8_bo3` (Liga 2026-27):**
  1. Primero el enfrentamiento directo: una minitabla con los cruces entre los empatados, a 3 la victoria y 1 el empate. Entre dos es su propio cruce.
  2. Después `diff_avg DESC`. Si empataron su cruce, decide la diferencia.
- **`balanced_ko4` (Mundial) y `liga_berger_ko8`:** `diff_avg DESC`.

Si aun así siguen igualados, comparten `rank`, y las eliminatorias no arrancan mientras el empate afecte al corte de clasificación.

`pts_total_vpv` se muestra como dato, pero **no** desempata.

Los formatos con grupos devuelven una entrada por grupo en `groups` (`label='A'`, `label='B'`…) y la UI las pinta lado a lado.

---

## Admin

Todos requieren `Authorization: Bearer <jwt>` de un usuario con `is_admin=true`.

### `POST /api/competitions/admin/season/{season_id}`

Crea un playoff, o devuelve el existente si ya hay uno con ese `name` en la temporada.

**Body:**

```json
{ "format_id": "liga_berger_ko8_bo3", "name": "Apertura" }
```

**Campos:**
- `name` distingue los playoffs de una misma temporada (`Apertura` / `Clausura`).
- Si se omite `name`, se usa `"Playoff — <nombre del formato>"`, que es lo que hace el torneo.
- `format_id` vale por defecto `balanced_ko4`.

**Respuesta `200`:** el `CompetitionDetail`, en estado `pending`.

**Errores:** `422` si `format_id` es desconocido.

---

### `POST /api/competitions/admin/{competition_id}/start-regular`

Genera el calendario de la fase de liga con un sorteo aleatorio (queda guardado en `config.seed`) y pasa el playoff a `regular`.

**Body:**

```json
{ "matchday_start": 6, "matchday_end": 16, "planned_ko_matchday_numbers": [17, 18, 19, 20, 21] }
```

**Campos:**
- `matchday_end - matchday_start + 1` tiene que coincidir con las jornadas que el formato pide para los participantes activos.
- `planned_ko_matchday_numbers` es opcional, pero recomendado:
  - si se da, las eliminatorias arrancan solas en cuanto se resuelve el último cruce de liga;
  - si se omite, hay que llamar a `start-ko` a mano.
- Su longitud tiene que coincidir con `n_rounds_ko`.

**Recálculo retroactivo.** Tras crear los cruces, se recalculan las jornadas del rango que ya tengan puntuación. Si la Apertura se crea con la J6 ya cerrada, sus cruces salen resueltos.

**Respuesta `200`:**

```json
{ "matchups_inserted": 55 }
```

Son 55 con 11 participantes en un todos contra todos (5 por jornada × 11) y 26 en `balanced_ko4`.

**Idempotente:** si ya hay cruces de liga, devuelve `{"matchups_inserted": 0}` y no toca nada.

**Errores `422`:**
- el rango no tiene las jornadas que pide el formato;
- el nº de jornadas KO no coincide;
- la temporada no tiene esas jornadas;
- el formato no admite ese número de participantes (`balanced_ko4` exige 13).

---

### `POST /api/competitions/admin/{competition_id}/start-ko`

Genera las eliminatorias con la clasificación de la fase de liga, que queda congelada en `config.regular_standings_snapshot` para los desempates. Pasa el playoff a `ko`.

Normalmente no hace falta llamarlo: se dispara solo si `start-regular` recibió `planned_ko_matchday_numbers`.

**Body:**

```json
{ "ko_matchday_numbers": [17, 18, 19, 20, 21] }
```

**Respuesta `200`:** `{"matchups_inserted": N}`.

| Formato | Jornadas KO | Cruces |
|---|---|---|
| `balanced_ko4` | 2 | 3: 2 semis (1-4, 2-3) y la final |
| `liga_berger_ko8` | 3 | 7: 4 cuartos, 2 semis y la final |
| `liga_berger_ko8_bo3` | 5 | 9: 4 cuartos (1-8, 4-5, 2-7, 3-6), 2 semis (ganador 1-8 contra ganador 4-5, ganador 2-7 contra ganador 3-6) y 3 jornadas de final |

**Idempotente:** si ya hay cruces de eliminatoria, devuelve `0`.

**Errores `422`:**
- el nº de jornadas KO no coincide;
- quedan cruces de liga sin resolver;
- alguna jornada no existe;
- hay un empate que el desempate no resuelve dentro del corte (ver abajo).

---

## Mensajes de error

| Status | `message` (ejemplo) | Causa típica |
|---|---|---|
| 422 | `Formato desconocido: foo` | `format_id` no registrado |
| 422 | `El formato liga_berger_ko8_bo3 requiere 11 jornadas para 11 participantes, recibidas 13` | Rango de liga mal, o formatos pedidos sin `season_id` |
| 422 | `El formato liga_berger_ko8_bo3 requiere 5 jornadas KO, recibidas 3` | Lista de jornadas KO incompleta |
| 422 | `La temporada no tiene jornadas 6..16 (encontradas 10 de 11).` | Faltan jornadas en BD |
| 422 | `Quedan 3 cruces de fase regular sin resolver. Termina la fase regular antes de iniciar las eliminatorias.` | Falta puntuar alguna jornada |
| 422 | `Empate sin desempate dentro del top-8 del playoff. Resuelve antes de iniciar las eliminatorias: rank 8: Ana, Luis` | Empate total en el corte (en `balanced_ko4`, «top-4») |
| 422 | `balanced_ko4 expects 13 participants, got 12` | La temporada no tiene los participantes que exige el formato |
| 404 | `Competition con id=99 no encontrado` | id incorrecto |

---

## Schemas

```ts
interface MatchupEntry {
  id: number;
  phase: "regular" | "ko";
  group_label: string | null;     // "overall" | "A" | "B" … (null en KO)
  round_label: string | null;     // "quarter" | "semi" | "final" (null en liga)
  round_number: number;           // KO sigue a la liga: 12, 13, 14… tras 11 jornadas
  matchday_id: number | null;
  matchday_number: number | null;
  participant_a_id: number | null;  // null en KO hasta que se decide el cruce previo
  participant_a_name: string | null;
  participant_b_id: number | null;
  participant_b_name: string | null;
  feeder_a_id: number | null;     // id del cruce que alimenta ese lado
  feeder_b_id: number | null;
  score_a: number | null;         // puntos VPV de la jornada; null = sin puntuar
  score_b: number | null;
  winner_participant_id: number | null;  // null = empate (liga) o jornada empatada de una final a 3
  winner_name: string | null;
}

interface StandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  group_label: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  rests: number;           // jornadas en que descansó
  points: number;          // 3*wins + 1*draws
  diff_avg: number;        // suma de (puntos propios - puntos del rival)
  pts_total_vpv: number;   // suma de puntos VPV en sus cruces (informativo)
}

interface FinalSeries {
  participant_a_id: number | null;   // ganador de la semi 1
  participant_a_name: string | null;
  participant_b_id: number | null;   // ganador de la semi 2
  participant_b_name: string | null;
  wins_a: number;                    // jornadas ganadas, incluidas las empatadas ya decididas
  wins_b: number;
  winner_participant_id: number | null;  // campeón; null mientras no esté decidido
  winner_name: string | null;
  legs: FinalLeg[];
}

interface FinalLeg {
  matchup_id: number;
  matchday_number: number | null;
  score_a: number | null;
  score_b: number | null;
  result: "a" | "b" | "pending" | "not_needed";
  decided_by: "points" | "difference" | "seed" | null;
}
```

---

## Recálculo automático

Cada vez que `ScoreAggregator.aggregate_matchday(matchday_id)` termina (scraping o cierre de jornada), invoca:

```python
CompetitionService(session).recalculate_matchups_for_matchday(matchday_id)
```

En cada competición afectada:
- **Resuelve los cruces de esa jornada.** En la liga, un empate da 1 punto a cada uno. En cuartos y semis, el empate lo gana el mejor clasificado. En una jornada de final a 3, el empate queda para la serie.
- **Escribe los ganadores** en los cruces siguientes.
- **Arranca las eliminatorias** si la liga terminó y había jornadas KO planificadas.
- **Marca el playoff como `completed`** cuando hay campeón: la final de una jornada tiene ganador, o la serie a 3 está decidida.

Es best-effort: cualquier excepción se registra como `competition matchup recalc failed for matchday_id=X` y el scraping sigue.
