# Telegram Alerts — Configuración por temporada

## Resumen

Cada temporada puede dirigir sus mensajes de Telegram a **canales/topics distintos**
y elegir **qué eventos** disparan alertas. Todo se configura desde
`/admin/temporadas` → seleccionar temporada.

```
+-------------------------------------------------+
|              Configuración Telegram             |
+---+-----------------------+---------------------+
|   | chat_id               | thread_id           |
+---+-----------------------+---------------------+
| 1 | telegram              | telegram_thread     |
|   | (Alineaciones)        | (Alineaciones)      |
| 2 | draft_telegram        | draft_telegram_thread
|   | (Picks del draft)     | (Topic del draft)   |
| 3 | alerts_telegram       | alerts_telegram_thread
|   | (Alertas)             | (Topic de alertas)  |
+---+-----------------------+---------------------+
```

Si no rellenas el chat dedicado de alertas, el sistema cae al chat
general (con su topic de alineaciones) y, en último término, al env
`TELEGRAM_ALERTS_CHAT_ID` o `TELEGRAM_CHAT_ID`.

## Eventos disponibles

| Evento | Hilo natural | Frecuencia | Fuente |
|---|---|---|---|
| `lineup_submitted` | Alineaciones | Cada vez que un participante guarda su alineación | [lineups/service.py](../backend/src/features/lineups/service.py) `_notify_telegram` |
| `deadline_reminder` | Alertas | 4h / 1h / 15min antes del deadline si quedan participantes sin alineación | [scraping/scheduler.py:425](../backend/src/features/scraping/scheduler.py#L425) |
| `live_match.goal` ⚽ | Alertas | En vivo | [scraping/live_monitor.py](../backend/src/features/scraping/live_monitor.py) |
| `live_match.assist` 👟 | Alertas | En vivo | idem |
| `live_match.yellow` 🟨 | Alertas | En vivo | idem |
| `live_match.red` 🟥 | Alertas | En vivo | idem |
| `live_match.sub_in` 🔼 | Alertas | En vivo | idem |
| `live_match.sub_out` 🔽 | Alertas | En vivo | idem |
| `live_match.penalty_committed` ⚠️ | Alertas | En vivo | idem |
| `live_match.woodwork` 🪵 | Alertas | En vivo | idem |
| `live_match.error_garrafal` 💥 | Alertas | En vivo | idem |
| `live_match.last_man_tackle` 🛡️ | Alertas | En vivo | idem |

**Por defecto todos están activos**. Desactiva los que no quieras
recibir desde el form de `/admin/temporadas`.

### Regla de propietario para eventos en vivo

El `live_monitor` aplica una regla extra que la UI NO controla
(hardcodeada en `live_monitor.py`):
- **Goles** se envían siempre (estén o no en propiedad de un participante VPV).
- El resto de subtipos sólo si el jugador implicado pertenece a un participante VPV de la temporada.

Esto evita el spam por jugadores no drafteados. Si en el futuro quieres
abrirlo, retoca la variable `always_send` en `live_monitor.py`.

## Tabla seasons — columnas relevantes

```sql
telegram_chat_id              VARCHAR(50)   -- alineaciones
telegram_thread_id            INTEGER
draft_telegram_chat_id        VARCHAR(50)   -- picks del draft
draft_telegram_thread_id      INTEGER
alerts_telegram_chat_id       VARCHAR(50)   -- canal dedicado de alertas
alerts_telegram_thread_id     INTEGER
alerts_config                 JSONB         -- per-event toggles
```

Migraciones idempotentes:
- `migration/schema/migrations/2026_06_12_add_alerts_telegram_columns.sql`
- `migration/schema/migrations/2026_06_12_add_alerts_config.sql`

## Estructura del JSONB `alerts_config`

```jsonc
{
  "events": {
    // Solo los DESACTIVADOS aparecen aquí. Lo no listado = activo.
    "deadline_reminder": false,
    "live_match.yellow": false,
    "live_match.sub_in": false
    // ...
  }
}
```

NULL o `{events: {}}` = todos los eventos activos (compat con seasons
pre-feature).

### Compatibilidad — kill switch legacy

La primera iteración tenía un toggle único `live_match_events`. Si tu
config persiste con `"live_match_events": false`, sigue funcionando
como **kill switch**: desactiva todos los subtipos `live_match.*` de
golpe. Al re-guardar desde la UI nueva se sobreescribe al esquema
granular automáticamente.

## Backend — flujo de resolución

### Resolución del **chat** (`TelegramNotifier.send_alert`)

[`backend/src/features/telegram/service.py`](../backend/src/features/telegram/service.py)

1. `season.alerts_telegram_chat_id` (con su thread propio) si está set.
2. `season.telegram_chat_id` (con su thread de alineaciones) si no.
3. `settings.telegram_alerts_chat_id` (env).
4. `telegram_settings.telegram_chat_id` (env global).

### Resolución del **evento** (¿se envía o no?)

[`backend/src/features/telegram/alerts_config.py`](../backend/src/features/telegram/alerts_config.py)

- `is_alert_event_enabled(cfg, key)` — para `deadline_reminder` y `lineup_submitted`.
- `is_live_event_enabled(cfg, event_type)` — para `live_match.{subtype}`:
  1. Si `events.live_match_events == false` ⇒ todos OFF (kill switch legacy).
  2. Si `events.live_match.{event_type} == false` ⇒ OFF.
  3. Si la clave no existe ⇒ ON (default).

Tests en
[`backend/tests/features/test_alerts_config.py`](../backend/tests/features/test_alerts_config.py)
fijan el contrato (14 casos).

## Herramienta: simulación de eventos en vivo

`simulate-live` te deja **validar tu config sin enviar nada**.

```bash
python -m src.features.scraping.cli simulate-live <season_id> \
  https://www.futbolfantasy.com/partidos/22196-mexico-sudafrica \
  https://www.futbolfantasy.com/partidos/22197-corea-del-sur-rep-checa
```

Output (resumido):

```jsonc
{
  "season_id": 9,
  "season_name": "Mundial 2026",
  "alerts_config": { "events": { "live_match.yellow": false } },
  "summary": {
    "matches": 2,
    "would_send_total": 14,
    "filtered_total": 16
  },
  "matches": [
    {
      "url": "...22196-mexico-sudafrica",
      "events_parsed": 30,
      "would_send": [
        { "event_type": "red", "player": "César Montes", "minute": "91:27",
          "rendered": "🟥 ROJA — César Montes (91:27)" }
      ],
      "filtered": [
        { "event_type": "yellow", "reason": "disabled in alerts_config (live_match.yellow=false)" },
        { "event_type": "sub_in",  "reason": "not VPV (and not in always_send list)" }
      ]
    }
  ]
}
```

Garantías del simulador:
- NO envía a Telegram.
- NO persiste en BD (`rollback` al final).
- Aplica los MISMOS filtros que `live_monitor` (ownership + alerts_config).
- La deduplicación in-memory se ignora a propósito: el simulador es
  para validar config, no para reproducir realidad histórica.

## Cómo añadir un evento de Telegram nuevo

### Nuevo evento global (no vinculado a un subtipo en vivo)

1. Constante en
   [`alerts_config.py`](../backend/src/features/telegram/alerts_config.py)
   (p.ej. `EVENT_RESULT_PUBLISHED`).
2. Añade al `ALERT_EVENTS` tuple.
3. Gate la fuente con `is_alert_event_enabled(season.alerts_config, EVENT_RESULT_PUBLISHED)`.
4. Checkbox en
   [`frontend/src/app/admin/temporadas/page.tsx`](../frontend/src/app/admin/temporadas/page.tsx).
5. Caso de test en `test_alerts_config.py`.

### Nuevo subtipo de evento en vivo (icono nuevo en futbolfantasy)

1. `ICON_MAP` en
   [`live_events.py`](../backend/src/features/scraping/live_events.py) — añade el filename → `event_type`.
2. `EVENT_EMOJI` + `EVENT_LABEL` con su icono y nombre.
3. `LIVE_EVENT_TYPES` en `alerts_config.py`.
4. Entrada en el grid del frontend con su emoji y label.
5. (Opcional) Si quieres que se envíe sin ser propiedad VPV, añade a
   `always_send` en `live_monitor.py`.

El gate y los defaults se enchufan solos (fallback a ON para subtipos
desconocidos).

## Despliegue

Migraciones idempotentes — pueden re-aplicarse sin riesgo:

```bash
psql -U vpv -d ligavpv -f /opt/vpv/migration/schema/migrations/2026_06_12_add_alerts_telegram_columns.sql
psql -U vpv -d ligavpv -f /opt/vpv/migration/schema/migrations/2026_06_12_add_alerts_config.sql
sudo systemctl restart vpv-backend
sudo -iu vpv bash -lc 'cd /opt/vpv/frontend && npm run build && pm2 restart vpv-frontend'
```

Verifica con:

```bash
psql -U vpv -d ligavpv -c "\d seasons" | grep -E 'alerts|telegram'
```

Esperado:
```
 telegram_chat_id          | character varying(50)
 telegram_thread_id        | integer
 draft_telegram_chat_id    | character varying(50)
 draft_telegram_thread_id  | integer
 alerts_telegram_chat_id   | character varying(50)
 alerts_telegram_thread_id | integer
 alerts_config             | jsonb
```

## Troubleshooting

| Síntoma | Diagnóstico |
|---|---|
| 500 en `/api/seasons` tras deploy | Faltan migraciones. Aplica las dos SQL de arriba. |
| Alertas siguen llegando al canal viejo | Verifica que rellenaste `alerts_telegram_chat_id` Y guardaste; mira el campo en BD con `SELECT alerts_telegram_chat_id FROM seasons WHERE id=...`. |
| Eventos en vivo no llegan | Comprueba `is_live_event_enabled`: corre `simulate-live` con la URL del partido y mira el campo `filtered` del JSON. |
| Subtipo deshabilitado SÍ llega | Verifica que has guardado (`SELECT alerts_config FROM seasons WHERE id=...` debería listar `live_match.<subtype>: false`). Si está, mira que el live_monitor lo logue: `journalctl -u vpv-backend -f \| grep live_monitor`. |
| Quiero deshabilitar TODAS las alertas en vivo de golpe | Desmarca los 10 checkboxes en la UI. O sql `UPDATE seasons SET alerts_config = '{"events": {"live_match_events": false}}' WHERE id=...;` (kill switch legacy). |

## Ficheros clave

| Capa | Fichero | Responsabilidad |
|---|---|---|
| Modelo | [shared/models/season.py](../backend/src/shared/models/season.py) | Columnas `alerts_*` |
| Helper | [features/telegram/alerts_config.py](../backend/src/features/telegram/alerts_config.py) | `is_alert_event_enabled`, `is_live_event_enabled` |
| Service | [features/telegram/service.py](../backend/src/features/telegram/service.py) | `send_alert`, `send_lineup_image` (con gate) |
| Scheduler | [features/scraping/scheduler.py](../backend/src/features/scraping/scheduler.py) | Recordatorios de deadline |
| Live monitor | [features/scraping/live_monitor.py](../backend/src/features/scraping/live_monitor.py) | Filtro per-subtype + dedup |
| Live parser | [features/scraping/live_events.py](../backend/src/features/scraping/live_events.py) | `ICON_MAP`, emojis y labels |
| CLI | [features/scraping/cli.py](../backend/src/features/scraping/cli.py) | `simulate-live` |
| Tests | [tests/features/test_alerts_config.py](../backend/tests/features/test_alerts_config.py) | 14 casos |
| Frontend | [app/admin/temporadas/page.tsx](../frontend/src/app/admin/temporadas/page.tsx) | UI agrupada por hilo + 10 checkboxes |
| Migraciones | `migration/schema/migrations/2026_06_12_*.sql` | Idempotentes |
