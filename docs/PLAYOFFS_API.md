# Playoffs — API reference

Endpoints expuestos por el módulo `features/competitions`. Prefijo:
`/api/competitions`.

Para uso operativo paso a paso ver [PLAYOFFS_RUNBOOK.md](PLAYOFFS_RUNBOOK.md).

---

## Discovery

### `GET /api/competitions/formats`

Lista los formatos de playoff disponibles. Lo usa la UI para poblar el desplegable.

**Auth**: ninguna (público).

**Respuesta `200`**:

```json
[
  {
    "format_id": "balanced_ko4",
    "display_name": "Balanced (4 partidos/uno) + KO top-4",
    "n_rounds_regular": 6,
    "n_rounds_ko": 2
  }
]
```

---

## Read endpoints (públicos)

### `GET /api/competitions/season/{season_id}`

Lista todas las competitions (playoff, otros) de una season.

**Respuesta `200`**:

```json
{
  "season_id": 11,
  "competitions": [
    {
      "id": 4,
      "season_id": 11,
      "name": "Playoff — Balanced (4 partidos/uno) + KO top-4",
      "type": "playoff",
      "status": "regular"
    }
  ]
}
```

---

### `GET /api/competitions/{competition_id}/matchups`

Todos los cruces de la competition con nombres ya joineados.

**Respuesta `200`** (extracto):

```json
{
  "competition": {
    "id": 4,
    "season_id": 11,
    "name": "Playoff — Balanced (4 partidos/uno) + KO top-4",
    "type": "playoff",
    "status": "regular",
    "config": {
      "format_id": "balanced_ko4",
      "seed": 1738291847,
      "matchday_range_regular": { "start": 1, "end": 6 }
    }
  },
  "matchups": [
    {
      "id": 101,
      "phase": "regular",
      "group_label": "overall",
      "round_label": null,
      "round_number": 1,
      "matchday_id": 50,
      "matchday_number": 1,
      "participant_a_id": 1,
      "participant_a_name": "Toni",
      "participant_b_id": 5,
      "participant_b_name": "Dani C",
      "feeder_a_id": null,
      "feeder_b_id": null,
      "score_a": 75,
      "score_b": 70,
      "winner_participant_id": 1,
      "winner_name": "Toni"
    }
  ]
}
```

`feeder_a_id` / `feeder_b_id` se rellenan en KO para semis y final cuando dependen del ganador de un cruce previo.

---

### `GET /api/competitions/{competition_id}/standings`

Clasificación calculada en vivo desde los matchups resueltos.

**Respuesta `200`**:

```json
{
  "competition": { "...": "..." },
  "groups": [
    {
      "label": "overall",
      "entries": [
        {
          "rank": 1,
          "participant_id": 7,
          "display_name": "3Cerros",
          "group_label": "overall",
          "played": 4,
          "wins": 4,
          "draws": 0,
          "losses": 0,
          "rests": 2,
          "points": 12,
          "diff_avg": 65,
          "pts_total_vpv": 365
        }
      ]
    }
  ]
}
```

Orden: `points DESC, diff_avg DESC, pts_total_vpv DESC, draft_order ASC`.

Para formatos con grupos, `groups` tiene N entradas (`label='A'`, `label='B'`, etc.) — la UI las renderiza lado a lado.

---

## Admin endpoints

Todos requieren `Authorization: Bearer <jwt>` con `is_admin=true`.

### `POST /api/competitions/admin/season/{season_id}`

Crea (o devuelve la existente) la competition de playoff para una season.

**Body**:

```json
{ "format_id": "balanced_ko4" }
```

**Respuesta `200`**: el `CompetitionDetail` completo. Idempotente.

**Errores**:
- `400 BusinessRuleError`: `format_id` desconocido.

---

### `POST /api/competitions/admin/{competition_id}/start-regular`

Genera el calendario de la fase regular (sorteo aleatorio).

**Body**:

```json
{
  "matchday_start": 1,
  "matchday_end": 6
}
```

**Respuesta `200`**:

```json
{ "matchups_inserted": 26 }
```

**Idempotente**: si ya hay matchups regular, devuelve `{"matchups_inserted": 0}`.

**Errores**:
- `400`: nº de jornadas distinto a `required_rounds_regular` del formato.
- `400`: el rango no cubre jornadas válidas en la season.

---

### `POST /api/competitions/admin/{competition_id}/start-ko`

Genera el bracket KO a partir de los standings de la fase regular.

**Body**:

```json
{ "ko_matchday_numbers": [7, 8] }
```

**Respuesta `200`**:

```json
{ "matchups_inserted": 3 }
```

Para `balanced_ko4`: 2 semis + 1 final con feeders.

**Errores**:
- `400`: nº jornadas KO distinto a `required_rounds_ko` del formato.
- `400`: hay cruces regular sin resolver.
- `400`: alguna jornada KO solicitada no existe en la season.

---

## Códigos de error comunes

| Status | Body `detail` ejemplo | Causa típica |
|---|---|---|
| 400 | `Formato desconocido: foo` | format_id no registrado |
| 400 | `El formato balanced_ko4 requiere 6 jornadas, recibidas 5` | rango incorrecto |
| 400 | `Quedan 3 cruces de fase regular sin resolver. ...` | falta scraping de alguna jornada |
| 400 | `balanced_ko4 expects 13 participants, got 12` | season con número de participantes incorrecto |
| 401 | `Token de autenticacion requerido` | falta `Authorization` |
| 403 | `Se requieren permisos de administrador` | usuario no admin |
| 404 | `Competition X no encontrada` | id incorrecto |

---

## Schemas (resumidos)

### `MatchupEntry`

```ts
{
  id: number;
  phase: "regular" | "ko";
  group_label: string | null;     // "overall" | "A" | "B" | ...
  round_label: string | null;     // "semi" | "final" | "quarter"
  round_number: number;
  matchday_id: number | null;
  matchday_number: number | null;
  participant_a_id: number | null;
  participant_a_name: string | null;
  participant_b_id: number | null;
  participant_b_name: string | null;
  feeder_a_id: number | null;     // id de otro matchup
  feeder_b_id: number | null;
  score_a: number | null;
  score_b: number | null;
  winner_participant_id: number | null;
  winner_name: string | null;
}
```

### `StandingEntry`

```ts
{
  rank: number;
  participant_id: number;
  display_name: string;
  group_label: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  rests: number;
  points: number;          // 3*wins + 1*draws
  diff_avg: number;        // sumatorio de (score_propio - score_rival)
  pts_total_vpv: number;
}
```

---

## Hook interno con scraping

Cada vez que `ScoreAggregator.aggregate_matchday(matchday_id)` termina, invoca:

```python
CompetitionService(session).recalculate_matchups_for_matchday(matchday_id)
```

Es best-effort: cualquier excepción se loggea como `competition matchup recalc failed for matchday_id=X` pero el scraping continúa. Esto asegura que los resultados del playoff van a la par del scraping sin trabajo manual.
