# Ciclo de vida de temporada — Liga VPV Fantasy

**Fecha**: 2026-03-18
**Estado**: Documentado, pendiente de implementar endpoints faltantes

## Estado actual de herramientas admin

### Funciona desde la web
- Editar config de temporada (status, jornadas, deadline, pool size)
- Editar scoring rules y pagos semanales (por temporada)
- Gestionar jornadas (toggle counts matchday/match)
- Scraping: trigger manual, start/stop scheduler, calendar sync
- Draft: crear, gestionar picks, draft en vivo
- Usuarios: activar/desactivar participantes, toggle admin/draft manager
- Backup de base de datos

### Requiere SQL manual o CLI
- Crear temporada nueva (`INSERT INTO seasons`)
- Importar equipos y jugadores (scraping inicial)
- Copiar scoring rules de temporada anterior
- Copiar season payments de temporada anterior
- Descargar fotos de jugadores (`python -m src.features.scraping.cli download-photos`)
- Actualizar scraping_season_slug (.env)

## Endpoints pendientes de implementar

### `POST /seasons/admin/initialize`
Crea temporada completa en un paso:
- Season record con status `setup`
- Copia scoring_rules de temporada anterior
- Copia season_payments de temporada anterior
- Crea season_participants
- Scrapea equipos + jugadores de futbolfantasy.com
- Crea 38 matchdays vacios

### `POST /seasons/admin/{season_id}/download-photos`
Expone como endpoint el CLI de descarga de fotos.

### `PUT /seasons/admin/{season_id}/finalize`
Marca temporada como `finished` con validaciones.

## Checklist completo: nueva temporada

### Paso 1 — Finalizar temporada actual
1. Verificar que todas las jornadas tienen `stats_ok`
2. Verificar pagos y clasificacion final
3. Cambiar status a `finished` (Admin → Temporadas)

### Paso 2 — Crear nueva temporada
1. Admin → Temporadas → "Nueva temporada" (pendiente de implementar)
   - Nombre: "2026-2027"
   - Slug scraping: "laliga-26-27"
   - Copiar config de: temporada anterior
   - Participantes: seleccionar usuarios
2. O via SQL:
```sql
INSERT INTO seasons (name, status, matchday_start, matchday_end, draft_pool_size, lineup_deadline_min)
VALUES ('2026-2027', 'setup', 1, 38, 26, 30);

-- Copiar scoring rules
INSERT INTO scoring_rules (season_id, rule_key, position, value, description)
SELECT NEW_SEASON_ID, rule_key, position, value, description
FROM scoring_rules WHERE season_id = OLD_SEASON_ID;

-- Copiar payments
INSERT INTO season_payments (season_id, payment_type, position_rank, amount, description)
SELECT NEW_SEASON_ID, payment_type, position_rank, amount, description
FROM season_payments WHERE season_id = OLD_SEASON_ID;

-- Participantes
INSERT INTO season_participants (season_id, user_id, draft_order, is_active)
SELECT NEW_SEASON_ID, user_id, 0, TRUE
FROM season_participants WHERE season_id = OLD_SEASON_ID AND is_active = TRUE;

-- Actualizar total
UPDATE seasons SET total_participants = (
    SELECT COUNT(*) FROM season_participants WHERE season_id = NEW_SEASON_ID
) WHERE id = NEW_SEASON_ID;
```

### Paso 3 — Importar equipos y jugadores
Via CLI (pendiente de endpoint):
```bash
# Actualizar .env: SCRAPING_SEASON_SLUG=laliga-26-27
sudo systemctl restart vpv-backend

# Importar calendario (crea matchdays + matches con equipos)
python -m src.features.scraping.cli update-calendar NEW_SEASON_ID

# Descargar fotos
python -m src.features.scraping.cli download-photos NEW_SEASON_ID
```

### Paso 4 — Configurar draft
1. Cambiar status a `draft` (Admin → Temporadas)
2. Ir a Drafts → Gestionar
3. Establecer orden de draft
4. Crear draft pretemporada (serpiente)
5. Ejecutar draft (via /drafts/live/{id} o manual)

### Paso 5 — Activar temporada
1. Cambiar status a `active` (Admin → Temporadas)
2. Establecer `matchday_current = 1`
3. El scheduler empieza a scrapear automaticamente

### Paso 6 — Draft invierno (a mitad de temporada)
1. En `matchday_winter`, calcular orden inverso a clasificacion
2. Cambiar status a `winter_draft`
3. Crear draft invierno (lineal)
4. Ejecutar draft
5. Volver status a `active`

### Paso 7 — Finalizar temporada
1. Cuando acaba La Liga, verificar datos completos
2. Cambiar status a `finished`
3. Generar premios finales (Admin → Economia)

## Config scraping por temporada

En `backend/.env`:
```
SCRAPING_SEASON_SLUG=laliga-25-26
```

Debe actualizarse al crear una nueva temporada y reiniciar el backend.
Futura mejora: almacenarlo en la tabla seasons para no requerir restart.
