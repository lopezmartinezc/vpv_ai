# API Reference — Liga VPV Fantasy

Base URL: `/api`

Swagger UI disponible en `/api/docs` cuando `DEBUG=true`.

## Autenticacion

JWT Bearer token via header `Authorization: Bearer <token>`.

- Token generado en `POST /api/auth/login`
- Expira en 480 minutos (8 horas)
- Algoritmo: HS256

Niveles de acceso:
- **Publico**: sin token
- **User**: token valido requerido
- **Admin**: token valido + `is_admin=true`

## Formato de errores

```json
{
  "code": "NOT_FOUND",
  "message": "Season 99 not found"
}
```

| Codigo | HTTP Status |
|--------|-------------|
| `AUTHENTICATION_ERROR` | 401 |
| `UNAUTHORIZED` | 403 |
| `NOT_FOUND` | 404 |
| `BUSINESS_RULE_VIOLATION` | 422 |
| `UNKNOWN_ERROR` | 500 |

---

## Health

### `GET /api/health`

Health check. Verifica conectividad con la base de datos.

**Auth**: Publico

**Response** `200`:
```json
{
  "status": "healthy",
  "database": true,
  "version": "0.1.0"
}
```

---

## Auth

### `POST /api/auth/login`

Autenticar usuario con username y password.

**Auth**: Publico

**Request**:
```json
{
  "username": "carlos",
  "password": "mi_password"
}
```

**Response** `200`:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

### `GET /api/auth/me`

Obtener datos del usuario autenticado.

**Auth**: User

**Response** `200`:
```json
{
  "id": 1,
  "username": "carlos",
  "display_name": "Carlos L.",
  "email": "carlos@example.com",
  "is_admin": true
}
```

### `POST /api/auth/refresh`

Renovar el token JWT.

**Auth**: User

**Response** `200`: Mismo formato que login.

### `GET /api/auth/invite/{token}`

Verificar validez de un token de invitacion.

**Auth**: Publico

**Response** `200`:
```json
{
  "valid": true,
  "target_user_id": 5,
  "target_display_name": "Daniel D.",
  "expired": false
}
```

### `POST /api/auth/register`

Registrar usuario (o poner password) usando token de invitacion.

**Auth**: Publico

**Request**:
```json
{
  "token": "abc123...",
  "username": "daniel",
  "password": "mi_password_seguro"
}
```

**Response** `200`: Mismo formato que login (auto-login tras registro).

### `POST /api/auth/admin/invite`

Crear invitacion para un usuario existente o nuevo.

**Auth**: Admin

**Request**:
```json
{
  "target_user_id": 5,
  "expires_days": 7
}
```

**Response** `200`:
```json
{
  "id": 1,
  "token": "abc123...",
  "target_user_id": 5,
  "target_display_name": "Daniel D.",
  "created_by_display_name": "Carlos L.",
  "expires_at": "2026-03-05T12:00:00",
  "used_at": null,
  "created_at": "2026-02-26T12:00:00"
}
```

### `GET /api/auth/admin/invites`

Listar todas las invitaciones.

**Auth**: Admin

**Response** `200`: `InviteResponse[]`

### `GET /api/auth/admin/users-without-password`

Listar usuarios que aun no tienen password (para crear invitaciones dirigidas).

**Auth**: Admin

**Response** `200`:
```json
[
  { "id": 5, "username": "daniel", "display_name": "Daniel D." }
]
```

### `GET /api/auth/admin/users`

Listar todos los usuarios con info administrativa.

**Auth**: Admin

**Response** `200`:
```json
[
  {
    "id": 1,
    "username": "carlos",
    "display_name": "Carlos L.",
    "email": "carlos@example.com",
    "is_admin": true,
    "has_password": true,
    "telegram_chat_id": "123456"
  }
]
```

### `PUT /api/auth/admin/users/{user_id}/toggle-admin`

Alternar el flag `is_admin` de un usuario.

**Auth**: Admin

**Response** `200`: `AdminUserResponse`

### `POST /api/auth/admin/users/{user_id}/reset-password`

Generar invitacion para que el usuario restablezca su password.

**Auth**: Admin

**Response** `200`: `InviteResponse`

---

## Seasons

### `GET /api/seasons`

Listar todas las temporadas.

**Auth**: Publico

**Response** `200`:
```json
[
  {
    "id": 8,
    "name": "2025-2026",
    "status": "active",
    "matchday_current": 25,
    "total_participants": 10
  }
]
```

### `GET /api/seasons/current`

Obtener la temporada activa (o la mas reciente).

**Auth**: Publico

**Response** `200`:
```json
{
  "id": 8,
  "name": "2025-2026",
  "status": "active",
  "matchday_start": 1,
  "matchday_end": 38,
  "matchday_current": 25,
  "matchday_winter": 20,
  "matchday_scanned": 24,
  "draft_pool_size": 15,
  "lineup_deadline_min": 15,
  "total_participants": 10,
  "created_at": "2025-08-01T00:00:00"
}
```

### `GET /api/seasons/formations`

Listar formaciones validas.

**Auth**: Publico

**Response** `200`:
```json
[
  { "id": 1, "formation": "1-4-4-2", "defenders": 4, "midfielders": 4, "forwards": 2 },
  { "id": 2, "formation": "1-4-3-3", "defenders": 4, "midfielders": 3, "forwards": 3 }
]
```

### `GET /api/seasons/{season_id}`

Detalle de una temporada.

**Auth**: Publico

**Response** `200`: `SeasonDetail` (mismo formato que `/current`)

### `GET /api/seasons/{season_id}/scoring-rules`

Reglas de puntuacion de una temporada.

**Auth**: Publico

**Response** `200`:
```json
[
  { "id": 1, "rule_key": "play", "position": null, "value": "1.00", "description": "Jugar" },
  { "id": 2, "rule_key": "goal", "position": "DEL", "value": "3.50", "description": "Gol delantero" }
]
```

### `GET /api/seasons/{season_id}/payments`

Pagos configurados para la temporada.

**Auth**: Publico

**Response** `200`:
```json
[
  { "id": 1, "payment_type": "initial_fee", "position_rank": null, "amount": "20.00", "description": "Cuota inicial" },
  { "id": 2, "payment_type": "weekly", "position_rank": null, "amount": "1.00", "description": "Pago semanal" }
]
```

### `PUT /api/seasons/admin/{season_id}`

Actualizar configuracion de la temporada.

**Auth**: Admin

**Request** (todos los campos opcionales):
```json
{
  "status": "active",
  "matchday_start": 1,
  "matchday_current": 25,
  "matchday_end": 38,
  "matchday_winter": 20,
  "lineup_deadline_min": 15,
  "draft_pool_size": 15
}
```

> Cuando cambia `matchday_start`, automaticamente se sincroniza `counts` en todas las jornadas (antes de inicio = `counts=false`).

**Response** `200`: `SeasonDetail`

### `PUT /api/seasons/admin/{season_id}/scoring-rules`

Actualizar reglas de puntuacion en lote.

**Auth**: Admin

**Request**:
```json
{
  "rules": [
    { "id": 1, "value": "1.50" },
    { "id": 2, "value": "4.00" }
  ]
}
```

**Response** `200`: `ScoringRuleResponse[]`

---

## Matchdays

### `GET /api/matchdays/{season_id}`

Listar jornadas de una temporada.

**Auth**: Publico

**Query params**:
- `stats_ok_only` (bool, default `true`): si `true`, solo jornadas con `stats_ok=true`

**Response** `200`:
```json
{
  "season_id": 8,
  "matchdays": [
    {
      "number": 25,
      "status": "finished",
      "counts": true,
      "stats_ok": true,
      "first_match_at": "2026-02-21T21:00:00"
    }
  ]
}
```

### `GET /api/matchdays/{season_id}/{number}`

Detalle de una jornada con partidos y puntuaciones.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "number": 25,
  "status": "finished",
  "counts": true,
  "stats_ok": true,
  "first_match_at": "2026-02-21T21:00:00",
  "matches": [
    {
      "id": 301,
      "home_team": "Athletic",
      "away_team": "Elche",
      "home_score": 2,
      "away_score": 1,
      "counts": true,
      "played_at": "2026-02-21T21:00:00"
    }
  ],
  "scores": [
    {
      "rank": 1,
      "participant_id": 3,
      "display_name": "Carlos L.",
      "total_points": 58,
      "formation": "1-4-3-3"
    }
  ]
}
```

### `GET /api/matchdays/{season_id}/{number}/lineup/{participant_id}`

Alineacion detallada de un participante en una jornada.

**Auth**: Publico

**Response** `200`:
```json
{
  "participant_id": 3,
  "display_name": "Carlos L.",
  "matchday_number": 25,
  "formation": "1-4-3-3",
  "total_points": 58,
  "players": [
    {
      "display_order": 1,
      "position_slot": "POR",
      "player_id": 101,
      "player_name": "Oblak",
      "photo_path": "photos/season_8/oblak.webp",
      "team_name": "Atletico",
      "points": 7,
      "score_breakdown": {
        "pts_play": 1, "pts_starter": 1, "pts_result": 2,
        "pts_clean_sheet": 3, "pts_goals": 0, "pts_assists": 0,
        "pts_yellow": 0, "pts_red": 0, "pts_marca": 0,
        "pts_as": 0, "pts_total": 7
      }
    }
  ],
  "bench": [
    {
      "player_id": 201,
      "player_name": "Ruiz",
      "photo_path": null,
      "position": "MED",
      "team_name": "Betis",
      "matchday_points": 3
    }
  ]
}
```

### `PUT /api/matchdays/admin/{season_id}/{number}`

Actualizar jornada (toggle counts, cambiar status).

**Auth**: Admin

**Request**:
```json
{
  "counts": false,
  "status": "finished"
}
```

**Response** `200`: `AdminMatchdayResponse`

### `PUT /api/matchdays/admin/{season_id}/{number}/match/{match_id}`

Actualizar partido individual (toggle counts, corregir resultado).

**Auth**: Admin

**Request**:
```json
{
  "counts": false,
  "home_score": 2,
  "away_score": 1
}
```

**Response** `200`: `AdminMatchResponse`

---

## Standings

### `GET /api/standings/{season_id}`

Clasificacion general de la temporada.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "season_name": "2025-2026",
  "entries": [
    {
      "rank": 1,
      "participant_id": 3,
      "display_name": "Carlos L.",
      "total_points": 1322,
      "matchdays_played": 24,
      "avg_points": 55.08
    }
  ]
}
```

> Solo computa jornadas donde `matchdays.counts=true` Y `matches.counts=true`.

---

## Squads

### `GET /api/squads/{season_id}`

Resumen de plantillas de todos los participantes.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "squads": [
    {
      "participant_id": 3,
      "display_name": "Carlos L.",
      "total_players": 15,
      "season_points": 1322,
      "positions": { "POR": 2, "DEF": 5, "MED": 5, "DEL": 3 }
    }
  ]
}
```

### `GET /api/squads/{season_id}/{participant_id}`

Plantilla completa de un participante.

**Auth**: Publico

**Response** `200`:
```json
{
  "participant_id": 3,
  "display_name": "Carlos L.",
  "season_points": 1322,
  "players": [
    {
      "player_id": 101,
      "display_name": "Oblak",
      "photo_path": "photos/season_8/oblak.webp",
      "position": "POR",
      "team_name": "Atletico",
      "season_points": 156
    }
  ]
}
```

---

## Drafts

### `GET /api/drafts/{season_id}`

Listar drafts de una temporada.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "drafts": [
    {
      "id": 1,
      "phase": "preseason",
      "draft_type": "snake",
      "status": "completed",
      "total_picks": 150,
      "started_at": "2025-08-15T10:00:00",
      "completed_at": "2025-08-15T12:00:00"
    }
  ]
}
```

### `GET /api/drafts/{season_id}/{phase}`

Detalle de un draft con participantes y picks.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "phase": "preseason",
  "draft_type": "snake",
  "status": "completed",
  "participants": [
    { "participant_id": 3, "display_name": "Carlos L.", "draft_order": 1 }
  ],
  "picks": [
    {
      "pick_number": 1,
      "round_number": 1,
      "participant_id": 3,
      "display_name": "Carlos L.",
      "draft_order": 1,
      "player_name": "Mbappe",
      "position": "DEL",
      "team_name": "Real Madrid"
    }
  ]
}
```

---

## Economy

### `GET /api/economy/{season_id}`

Balances economicos de todos los participantes.

**Auth**: Publico

**Response** `200`:
```json
{
  "season_id": 8,
  "balances": [
    {
      "participant_id": 3,
      "display_name": "Carlos L.",
      "initial_fee": "20.00",
      "weekly_total": "24.00",
      "draft_fees": "5.00",
      "net_balance": "49.00"
    }
  ]
}
```

### `GET /api/economy/{season_id}/{participant_id}`

Detalle economico de un participante con transacciones.

**Auth**: Publico

**Response** `200`:
```json
{
  "participant_id": 3,
  "display_name": "Carlos L.",
  "net_balance": "49.00",
  "transactions": [
    {
      "id": 1,
      "type": "initial_fee",
      "amount": "20.00",
      "description": "Cuota inicial temporada",
      "matchday_number": null,
      "created_at": "2025-08-01T00:00:00"
    }
  ]
}
```

### `POST /api/economy/admin/{season_id}/transaction`

Crear transaccion manual.

**Auth**: Admin

**Request**:
```json
{
  "participant_id": 3,
  "type": "manual_adjustment",
  "amount": "5.00",
  "description": "Multa por no poner alineacion",
  "matchday_id": null
}
```

Tipos validos: `initial_fee`, `weekly_payment`, `winter_draft_fee`, `prize`, `manual_adjustment`, `penalty`

**Response** `200`: `TransactionEntry`

### `DELETE /api/economy/admin/{season_id}/transaction/{tx_id}`

Eliminar una transaccion.

**Auth**: Admin

**Response** `200`:
```json
{ "deleted": true }
```

---

## Scraping

### `POST /api/scraping/matchday/{season_id}/{number}`

Scrapear estadisticas de todos los jugadores de una jornada.

**Auth**: Publico (deberia ser Admin — considerar proteger)

**Response** `200`:
```json
{ "processed": 220, "skipped": 10, "errors": 2 }
```

### `POST /api/scraping/match/{season_id}/{number}/{match_id}`

Scrapear estadisticas de un partido individual.

**Auth**: Publico

**Response** `200`:
```json
{ "processed": 44, "skipped": 2, "errors": 0 }
```

### `POST /api/scraping/calendar/{season_id}`

Actualizar resultados y fechas de partidos desde el calendario de La Liga.

**Auth**: Publico

**Response** `200`:
```json
{ "scores_updated": 5, "dates_updated": 12 }
```

### `POST /api/scraping/check-updates`

Verificar si hay cambios en la homepage (CRC change detection).

**Auth**: Publico

**Response** `200`:
```json
{ "changed": true, "ready_match_ids": [20301, 20302] }
```

### `GET /api/scraping/admin/status`

Estado del scheduler.

**Auth**: Admin

**Response** `200`:
```json
{
  "running": true,
  "poll_interval_seconds": 900,
  "last_tick_at": "2026-02-26T15:30:00+00:00",
  "next_run_at": "2026-02-26T15:45:00+00:00",
  "lock_held": false,
  "last_calendar_sync_at": "2026-02-26T06:00:00+00:00",
  "next_calendar_sync_at": "2026-02-27T06:00:00+00:00"
}
```

### `POST /api/scraping/admin/trigger`

Forzar un tick manual del scheduler.

**Auth**: Admin

**Response** `200`:
```json
{ "triggered": true }
```

### `POST /api/scraping/admin/start`

Iniciar el scheduler.

**Auth**: Admin

**Response** `200`: `SchedulerStatus`

### `POST /api/scraping/admin/stop`

Detener el scheduler.

**Auth**: Admin

**Response** `200`: `SchedulerStatus`
