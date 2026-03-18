# Ciclo de vida de temporada — Liga VPV Fantasy

**Fecha**: 2026-03-18
**Estado**: Endpoints implementados, pendiente frontend + migración producción

## Estado actual de herramientas admin

### Funciona desde la web
- Editar config de temporada (status, jornadas, deadline, pool size)
- Editar scoring rules y pagos semanales (por temporada)
- Gestionar jornadas (toggle counts matchday/match)
- Scraping: trigger manual, start/stop scheduler, calendar sync
- Draft: crear, gestionar picks, draft en vivo
- Usuarios: activar/desactivar participantes, toggle admin/draft manager
- Backup de base de datos
- **Crear temporada nueva** (`POST /api/seasons/admin/initialize`)
- **Importar equipos y jugadores** (background task del initialize)
- **Descargar fotos de jugadores** (`POST /api/seasons/admin/{id}/download-photos`)
- **Finalizar temporada** (`PUT /api/seasons/admin/{id}/finalize`)

### Requiere intervención manual
- Migración DB en producción: `ALTER TABLE seasons ADD COLUMN scraping_slug VARCHAR(50);`
- Actualizar `scraping_slug` de temporada actual: `UPDATE seasons SET scraping_slug = 'laliga-25-26' WHERE id = 8;`

## Endpoints implementados

### `POST /api/seasons/admin/initialize`
Crea temporada completa en un paso:
- Season record con status `setup` y `scraping_slug`
- Copia scoring_rules de temporada anterior (si `copy_from_season_id`)
- Copia season_payments de temporada anterior
- Crea season_participants (de lista explícita o copiando del source)
- Crea 38 matchdays vacíos
- **Background task**: scrapea equipos + jugadores + calendario de futbolfantasy.com

Request body:
```json
{
  "name": "2026-2027",
  "scraping_slug": "laliga-26-27",
  "matchday_start": 1,
  "matchday_end": 38,
  "draft_pool_size": 26,
  "lineup_deadline_min": 30,
  "copy_from_season_id": 8,
  "participant_user_ids": null
}
```

### `POST /api/seasons/admin/{season_id}/download-photos`
Descarga fotos de jugadores de futbolfantasy.com. Usa `scraping_slug` de la temporada.
Retorna: `{"downloaded": N, "skipped": N, "errors": N, "restored": N}`

### `PUT /api/seasons/admin/{season_id}/finalize`
Marca temporada como `finished`. **Bloquea** si hay jornadas con `counts=TRUE` sin `stats_ok=TRUE`.

## Checklist completo: nueva temporada

### Paso 1 — Finalizar temporada actual
1. Verificar que todas las jornadas tienen `stats_ok`
2. Verificar pagos y clasificación final
3. `PUT /api/seasons/admin/{id}/finalize`

### Paso 2 — Crear nueva temporada
1. `POST /api/seasons/admin/initialize` con:
   - `name`: "2026-2027"
   - `scraping_slug`: "laliga-26-27"
   - `copy_from_season_id`: ID de temporada anterior
2. Esperar ~2-3 minutos para que el background task importe equipos, jugadores y calendario
3. Verificar en `GET /api/seasons/{new_id}` que hay equipos y jugadores

### Paso 3 — Descargar fotos
1. `POST /api/seasons/admin/{new_id}/download-photos`
2. Proceso tarda ~5 minutos

### Paso 4 — Configurar draft
1. Cambiar status a `draft` (Admin → Temporadas)
2. Ir a Drafts → Gestionar
3. Establecer orden de draft
4. Crear draft pretemporada (serpiente)
5. Ejecutar draft (via /drafts/live/{id} o manual)

### Paso 5 — Activar temporada
1. Cambiar status a `active` (Admin → Temporadas)
2. Establecer `matchday_current = 1`
3. El scheduler empieza a scrapear automáticamente (usa `scraping_slug` de la DB)

### Paso 6 — Draft invierno (a mitad de temporada)
1. En `matchday_winter`, calcular orden inverso a clasificación
2. Cambiar status a `winter_draft`
3. Crear draft invierno (lineal)
4. Ejecutar draft
5. Volver status a `active`

### Paso 7 — Finalizar temporada
1. Cuando acaba La Liga, verificar datos completos
2. `PUT /api/seasons/admin/{id}/finalize`
3. Generar premios finales (Admin → Economía)

## Config scraping por temporada

El `scraping_slug` ahora se almacena en la tabla `seasons` (columna `scraping_slug`).
El backend lo lee de la DB primero, con fallback a `.env` para compatibilidad.

Migración necesaria en producción:
```sql
ALTER TABLE seasons ADD COLUMN scraping_slug VARCHAR(50);
UPDATE seasons SET scraping_slug = 'laliga-25-26' WHERE id = 8;

CREATE TABLE push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_push_subscriptions_user ON push_subscriptions(user_id);
```

Variables de entorno nuevas en `.env`:
```env
VAPID_PUBLIC_KEY=<clave publica base64url>
VAPID_PRIVATE_KEY=<path al private_key.pem>
VAPID_SUBJECT=mailto:admin@ligavpv.com
TELEGRAM_ALERTS_CHAT_ID=<chat_id del grupo de alertas>
```

Nginx: agregar bloque para service worker:
```nginx
location = /sw.js {
    root /opt/vpv/frontend/public;
    try_files /sw.js =404;
    add_header Cache-Control "no-cache";
    add_header Service-Worker-Allowed "/";
}
```
