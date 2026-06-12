# Roadmap de Mejoras — Liga VPV Fantasy

**Fecha**: 2026-05-22
**Estado**: En progreso

## Estado actual

La app esta en produccion (new.ligavpv.com) con todas las funcionalidades core:
- Frontend Next.js + Tailwind, backend FastAPI + SQLAlchemy 2.0 async
- PostgreSQL con `seasons.kind` discriminado: Liga (`league`) + Torneos (`tournament`, Mundial 26 / futuras Eurocopas y Copa America)
- Tabla `tournament_predictions` con columna `bracket_predictions JSONB` (orden de grupos, mejores terceros, ganadores knockout)
- Liga, Copa, Drafts, Alineaciones, Economia, Scraping automatico, Admin completo
- Mundial: pagina `/grupos`, `/bracket` (cuadro FIFA dos lados), wizard de predicciones extendido (privado `/mis-predicciones`), ranking publico expandible (`/predicciones`) y motor de auto-scoring (`/api/tournaments/admin/{season_id}/predictions/recalculate`)
- Banderas nacionales (271 SVGs, `flag-icons` CC-BY-4.0) en grupos / bracket / predicciones via `<CountryFlag>` + mapeo nombre->ISO
- Drag & drop con `@dnd-kit/*` en el wizard de predicciones (orden de grupos, best thirds picker, bracket interactivo)
- Deadline lock: las predicciones se cierran al primer partido del torneo (`first_match_at - lineup_deadline_min`); endpoint `GET /predictions/status` informa al frontend

---

## Prioridad 1 — Alto impacto, complejidad baja-media

### 1.1 Countdown al deadline de alineacion
- **Problema**: Los usuarios no saben cuanto tiempo les queda para enviar alineacion
- **Solucion**: Banner/widget en home y pagina de alineacion con cuenta atras
- **Datos**: `matchday.first_match_at - season.lineup_deadline_min`
- **Archivos**: `frontend/src/components/dashboard/deadline-widget.tsx`, `page.tsx`
- **Complejidad**: Baja
- **Estado**: [x] Completado (2026-03-17)
- **Notas**: Incluye logica de mostrar jornada anterior hasta que pase el deadline

### 1.2 Historial de alineaciones del usuario
- **Problema**: Un usuario no puede ver sus alineaciones pasadas
- **Solucion**: Endpoint `GET /lineups/{season_id}/history` + seccion en `/perfil` con cards expandibles
- **Implementacion**: cards colapsables por jornada (mas reciente arriba), click expande para ver 11 jugadores con foto, posicion, puntos
- **Complejidad**: Baja
- **Estado**: [x] Completado (2026-03-19)
- **Notas**: Tambien se movio cambio de contraseña a accordion colapsado. Racha de forma (ultimos 5 partidos) añadida a la seleccion de alineacion.

### 1.3 Estadisticas publicas (no solo admin)
- **Problema**: `/admin/estadisticas` solo accesible para admin
- **Solucion**: Crear `/estadisticas` publico con tabs Jugadores y Liga
- **Backend**: endpoints `/stats/{season_id}/players` y `/stats/{season_id}/league` ya no requieren auth
- **Frontend**: nueva pagina reutilizando componentes existentes
- **Complejidad**: Baja
- **Estado**: [ ] Pendiente

### 1.4 Notificaciones automaticas de deadline
- **Problema**: Notificaciones Telegram son manuales (admin pulsa boton), usuarios olvidan enviar alineacion
- **Solucion**: Sistema de 3 canales: Telegram (grupo alertas), Push PWA (notificacion nativa), Banner agresivo en la app
- **Implementacion**:
  - Scheduler job `deadline_reminder` envia a 2h y 30min del deadline
  - Telegram: mensaje al grupo de alertas (`TELEGRAM_ALERTS_CHAT_ID`, separado de alineaciones)
  - Push: Web Push API con VAPID keys, service worker, subscription en frontend
  - Banner: sticky rojo/naranja en todas las paginas cuando faltan <2h y no has enviado
  - Endpoint `GET /lineups/{season_id}/deadline-status` para el banner
  - Endpoints admin: `POST /notifications/admin/test-push` y `test-reminder`
  - Botones de test en Admin > Telegram
- **Complejidad**: Media-Alta
- **Estado**: [x] Completado (2026-03-18)
- **Notas**: Nueva tabla `push_subscriptions`. Env vars: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `TELEGRAM_ALERTS_CHAT_ID`
- **2026-06-12**: configuracion per-season ampliada con canal/topic
  dedicado de alertas (`alerts_telegram_chat_id`) y opt-out por evento
  (incluido per-subtype para eventos en vivo: gol/amarilla/cambio/...).
  Doc: [`docs/TELEGRAM_ALERTS.md`](TELEGRAM_ALERTS.md). CLI
  `simulate-live` para ensayar la config sin enviar.

### 1.5 Desglose de puntos en la jornada
- **Problema**: Usuarios ven puntos totales pero no el desglose
- **Solucion**: Expandir cada jugador para ver pts_play, pts_result, pts_goals, etc.
- **Complejidad**: Baja
- **Estado**: [x] Ya existia (MatchdayAccordion con PlayerRow expandible)
- **Notas**: Click en jugador muestra grid con 10 categorias de puntos (solo no-cero)

---

## Prioridad 2 — Impacto medio, complejidad media

### 2.1 Comparador de plantillas (head-to-head)
- **Problema**: No se pueden comparar dos participantes lado a lado
- **Solucion**: Pagina `/comparar` con enfrentamientos directos, diferencia de puntos, jugadores en comun
- **Backend**: endpoint cruzando `participant_matchday_scores` + `lineups`
- **Complejidad**: Media
- **Estado**: [ ] Pendiente

### 2.2 MVP por jornada
- **Problema**: No hay destacados por jornada
- **Solucion**: Badges en vista de jornada: MVP (mas puntos alineado), flop, mas goles
- **Datos**: `player_stats` + `lineup_players`
- **Complejidad**: Baja
- **Estado**: [ ] Pendiente

### 2.3 Grafico de evolucion personal
- **Problema**: No hay vista personal del progreso del usuario
- **Solucion**: Dos graficos en `/perfil` (puntos por jornada + posicion en liga) + stats cards
- **Backend**: reutiliza `/standings/{id}/evolution` existente, filtrado en frontend
- **Complejidad**: Media
- **Estado**: [x] Completado (2026-03-17)
- **Notas**: Stats: mejor/peor jornada, posicion media, mejor racha top 3

### 2.4 Plantillas mejoradas
- **Problema**: Vista de plantillas basica
- **Solucion**: Puntos totales por jugador, % jornadas alineado, MVP de plantilla, distribucion posicional
- **Complejidad**: Media
- **Estado**: [ ] Pendiente

### 2.5 Acierto de Mister (Manager Accuracy)
- **Problema**: Los usuarios no saben si eligen bien su XI de entre sus 26 jugadores
- **Solucion**: Calculo de alineacion optima por jornada (prueba 7 formaciones) vs lo que pusiste
- **Implementacion**:
  - Perfil: seccion con accuracy media, semanas perfectas, puntos perdidos + lista expandible por jornada con missed calls
  - Pagina `/acierto`: ranking publico de todos los participantes + filtro por jornada
  - Detalle por jornada: XI actual vs XI optimo lado a lado, jugadores en rojo/verde, cambios sugeridos
  - Usa `player_ownership_log` para propiedad historica correcta (draft invierno)
  - Respeta `match.counts` y `player_stats.position` (fuente de verdad)
- **Complejidad**: Alta
- **Estado**: [x] Completado (2026-03-19)
- **Notas**: Endpoint `GET /lineups/{season_id}/accuracy` (personal) + `GET /lineups/{season_id}/accuracy/ranking?matchday=N` (publico). Racha de forma (ultimos 5 partidos) tambien añadida a la seleccion de alineacion.

### 2.6 Info enriquecida en seleccion de alineacion
- **Problema**: Los jugadores solo mostraban nombre, equipo y posicion al elegir alineacion
- **Solucion**: Dos niveles de informacion:
  - **Todos los usuarios**: racha ultimos 5 partidos (cuadrados coloreados W/D/L con puntos) + stats (imbatibilidades POR/DEF, goles, asistencias, tarjetas)
  - **Solo admin**: predicciones xPts, rival + casa/fuera, % titular, tendencia (datos del endpoint de predicciones)
- **Complejidad**: Media
- **Estado**: [x] Completado (2026-03-19)
- **Notas**: Backend: `recent_form` en `SquadPlayerForLineup` con `get_squad_recent_form()`. Frontend: admin fetch de `/stats/{season_id}/predictions`. `starter_pct` viene ya como porcentaje del backend.

---

## Prioridad 3 — Features nuevos, complejidad alta

### 3.1 Sistema de logros/badges
- **Problema**: No hay gamificacion mas alla de la clasificacion
- **Solucion**: Badges automaticos (racha victorias, MVP consecutivo, draft steal, etc.)
- **Implementacion**: nueva tabla `achievements` + logica post-jornada
- **Complejidad**: Alta
- **Estado**: [ ] Pendiente

### 3.2 Draft en vivo (WebSocket)
- **Problema**: Draft sin experiencia en tiempo real
- **Solucion**: WebSocket broadcast + pagina interactiva /drafts/live/{id}
- **Complejidad**: Alta
- **Estado**: [x] Completado (2026-03-18)
- **Notas**: Cada participante elige desde su dispositivo. Admin puede forzar picks. Filtros: texto + posicion + equipo. Admin: stats avanzadas + sugerencias top 5 por posicion.

### 3.3 Predicciones pre-jornada
- **Problema**: No hay herramienta para predecir puntos esperados
- **Solucion**: xPts = forma EWMA (40%) + media temporada (20%) + factor rival (25%) + casa/fuera (15%)
- **Complejidad**: Alta
- **Estado**: [x] Completado (2026-03-18)
- **Notas**: Admin only. Factor rival invertido para POR/DEF vs MED/DEL. Ranking dificultad rivales. Starter %, penalty taker, rival reciente (5 partidos).

---

## Prioridad 4 — Mejoras tecnicas/operativas

### 4.1 PWA (Progressive Web App)
- **Problema**: App no instalable en movil
- **Solucion**: Manifest + iconos (192, 512, apple-touch-icon, OG image) + metadata completa
- **Complejidad**: Baja
- **Estado**: [x] Completado (2026-03-17)
- **Notas**: Sin service worker offline (datos siempre necesitan servidor)

### 4.2 Lazy loading en tablas largas
- **Problema**: Tablas de 200+ jugadores cargan completas
- **Solucion**: Paginacion o virtual scrolling
- **Complejidad**: Media
- **Estado**: [ ] Pendiente

### 4.3 Tests automatizados
- **Problema**: No hay tests
- **Solucion**: Tests de endpoints criticos (login, lineup submission, scoring)
- **Complejidad**: Alta
- **Estado**: [ ] Pendiente

### 4.5 Ciclo de vida de temporada (admin)
- **Problema**: Crear temporada requeria SQL manual y CLI
- **Solucion**: 3 endpoints admin + UI en /admin/temporadas:
  - `POST /seasons/admin/initialize` — crea temporada, copia config, importa equipos/jugadores en background
  - `POST /seasons/admin/{id}/download-photos` — descarga fotos de jugadores
  - `PUT /seasons/admin/{id}/finalize` — finaliza temporada con validacion de stats
- **Extras**: `scraping_slug` almacenado en DB (ya no requiere reiniciar backend)
- **Complejidad**: Media
- **Estado**: [x] Completado (2026-03-18)
- **Notas**: Documentacion completa en `docs/SEASON_LIFECYCLE.md`

### 4.6 Palmares historico
- **Problema**: No habia vista del historial de la liga a traves de las temporadas
- **Solucion**: Pagina `/palmares` con campeonatos, ranking historico y records all-time
- **Complejidad**: Media
- **Estado**: [x] Completado (2026-03-19)

### 4.7 Grupos de participantes
- **Problema**: La liga tiene 3 grupos (Virtuales, Petit Comite, Vacas Sagradas) que compiten entre si. El ultimo grupo paga pica-pica en el siguiente draft.
- **Solucion**: Campo `group_name` en `season_participants`. Clasificacion de grupos en `/clasificacion` y home. Historial de grupos en `/palmares`. Admin asigna grupos en Admin > Usuarios.
- **Grupos**: Virtuales, Petit Comite, Vacas Sagradas, Comando Badalona
- **Ranking**: por media de puntos por miembro (pts/usr), no suma directa — justo si los grupos tienen distinto tamaño
- **Complejidad**: Media
- **Estado**: [x] Completado (2026-03-19)
- **Notas**: Migracion: `ALTER TABLE season_participants ADD COLUMN group_name VARCHAR(50);`. Ultimo grupo paga pica-pica.

---

## Prioridad 5 — Torneos (Mundial 2026, Eurocopa, ...)

### 5.1 Infraestructura de torneos
- **Problema**: Hospedar el Mundial 2026 (y futuros torneos) junto con la Liga sin duplicar BD ni dominio.
- **Solucion**: Discriminador `seasons.kind` (`league` | `tournament`), `tournament_type` (mundial / eurocopa / ...), `tournament_config` JSONB con `groups.matchdays`, `knockout.rounds[].pairings` (codigo + placeholders FIFA), reglas de scoring, etc.
- **Frontend**: `SeasonContext` extendido con `isTournamentContext`, `activeLeague`, `activeTournament`; persistencia en `localStorage`. Banner tematizado (`TournamentHero`) con emblema FIFA + patron de globo; clase `body.tournament-mundial` override de variables CSS; menus y sidebars admin se adaptan al contexto.
- **Scraping**: Helper `competition_url_prefix(kind, tournament_type)` (mundial -> world-cup, eurocopa -> eurocopa, ...). `parse_teams` soporta atributos `alt`/`title` y rutas absolutas. `_resolve_season_year` admite formatos "Mundial 26" / "2025-2026".
- **Estado**: [x] Completado (2026-05) — Fases 1-6.

### 5.2 Grupos, cuadro y predicciones del torneo
- **Pagina Grupos**: `/grupos` calcula clasificacion por `tournament_group` reusando los matchdays declarados como fase de grupos.
- **Pagina Cuadro de Eliminatorias**: `/bracket` con layout FIFA de dos lados (R32 -> Final centrada con tercer puesto). Mobile fallback a vista linear. Placeholders entendidos: `1A`/`2A`/`3:ABCDF` (clasificacion de grupo o mejor tercero), `WXX`/`LXX` (ganador/perdedor de partido `MXX`).
- **Admin Grupos**: `/admin/grupos` para asignar equipos a grupos `A`-`L`.
- **Predicciones extendidas**: Wizard de 3 pasos en `/predicciones`:
  1. **Generales** — campeon, sorpresa, goleador, MVP, notas.
  2. **Grupos** — para cada uno de los 12 grupos, ranking 1º-4º con deduplicacion.
  3. **Eliminatoria** — picker de 8 mejores terceros (capado a 8) + bracket interactivo donde el usuario clica para escoger ganador. La cadena se resuelve dinamicamente (`1A` -> `groups.A[0]`, `WXX` -> `match_winners.MXX`, `LXX` -> el otro equipo del partido `MXX`, `3:ABCDF` -> mejor tercero entre los grupos pasados).
- **Almacenamiento**: tabla `tournament_predictions` con columna `bracket_predictions JSONB` (estructura `{groups, best_thirds, match_winners}`).
- **Estado**: [x] Completado (2026-05) — Fases A-D.

### 5.3 Motor de auto-scoring de predicciones
- **Problema**: Calcular `bonus_points` por participante comparando su prediccion con los resultados reales tras cada ronda.
- **Solucion**:
  - `DEFAULT_PREDICTIONS_SCORING` (16 reglas, ver `docs/API.md`). Overridable via `tournament_config.predictions_scoring`.
  - `_compute_actuals(season)` deriva del estado actual: campeon (ganador del round con un solo partido tipo "Final"), top scorer (max goles agregados en jornadas del torneo), best player (max `pts_total` agregado), orden de grupos (mismo calculo que `/groups`), 8 mejores terceros (ranking pts -> gd -> gf), `match_winners` por `match_code` y `semifinalists` (winners de QF).
  - `_score_one(pred, actuals, rules)` produce `(total, detail)` con desglose por regla. Sorpresa (`dark_horse`) cuenta si llega a SF y no es el campeon. KO se puntua por tamaño de ronda (`ko_r32`/`ko_r16`/`ko_qf`/`ko_sf`/`ko_third_place`/`ko_final`).
  - Endpoint admin `POST /api/tournaments/admin/{season_id}/predictions/recalculate` recorre todas las predicciones, actualiza `bonus_points` y devuelve el ranking con detalle.
- **Frontend**: Boton "Recalcular puntos" en cabecera del Ranking de predicciones, visible solo si `user.isAdmin`.
- **Estado**: [x] Completado (2026-05-21) — Fase E.

### 5.4 Banderas nacionales + UX bracket interactivo
- **Problema**: Los escudos de federacion son poco reconocibles; el wizard de predicciones (selects/checkboxes) era engorroso en mobile y no mostraba el arbol del cuadro.
- **Banderas**:
  - 271 SVGs en `frontend/public/flags/` desde `flag-icons` (CC-BY-4.0), ~2.7 MB.
  - `frontend/src/lib/country-flags.ts`: mapeo `nombre/slug -> ISO 3166-1 alpha-2`; `normalize()` ignora acentos, puntos, guiones (`Rep. Checa` -> `rep checa`, `Bosnia-Herzegovina` -> `bosnia herzegovina`). 120+ variantes en castellano (catar, rd congo, chequia, ...).
  - `<CountryFlag teamName fallbackLogo>` (en `components/ui/country-flag.tsx`) muestra bandera o cae al logo del club. Usado en `/grupos`, `/bracket`, `/predicciones` (selects, ranking, bracket).
  - Standalone Next.js no sirve `public/`. Script `postbuild` en `package.json` copia `public/` y `.next/static/` al output: `cp -rT public .next/standalone/public ; cp -rT .next/static .next/standalone/.next/static`.
- **Drag & drop en `/predicciones`** (`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`):
  - Step 2 Grupos: lista vertical sortable de 4 cards por grupo; ordinal 1º-4º derivado de la posicion.
  - Step 3 Best Thirds: dos paneles "Clasifican (8)" / "Disponibles" con drag entre columnas.
  - Step 3 Bracket: layout FIFA dos lados (`InteractiveTwoSidedBracket` calculado con `computeBracketLayout` que reconstruye el arbol desde los placeholders `W*`/`L*`); cada slot acepta click rapido o long-press + drag al lado opuesto. Multi-candidato (`3:ABCDF`) cae a `<select>`. Mobile usa `InteractiveLinearBracket`.
  - Sensores: `MouseSensor { distance: 5 }` + `TouchSensor { delay: 200-250, tolerance: 5 }`. Chips con `touch-action: none` para que el browser no intercepte el drag.
- **Auto-relleno de grupos**: `useEffect([teams, myPred])` rellena `bracket_predictions.groups[letter]` con el orden por defecto del scraping en cuanto cargan los equipos. Asi los placeholders `1A`/`2B` del bracket resuelven sin que el user tenga que arrastrar nada.
- **Estado**: [x] Completado (2026-05-21).

### 5.5 Predicciones publica/privada + deadline lock + audit is_active
- **Split public/private** (commit `dba4b2d`):
  - `/predicciones` (publica, sin login) — ranking de aciertos del torneo con tabla y filas expandibles. Click en una fila muestra el detalle completo del participante: orden 1º-4º por grupo, badges de best thirds y ganadores de eliminatoria agrupados por ronda. Boton "Mis predicciones" en el header.
  - `/mis-predicciones` (privada, requiere login) — el wizard de 3 pasos (Generales / Grupos / Eliminatoria) con DnD. Banner si esta cerrado, link "← Ver predicciones de todos" arriba.
- **Deadline lock** (commit `d5ee6fa`):
  - `GET /api/tournaments/{season_id}/predictions/status` (publico) devuelve `{locked, deadline_at, first_match_at}`.
  - Deadline = `first_match_at` de la jornada 1 menos `seasons.lineup_deadline_min` (reusa el campo de Liga, default 30 min antes).
  - `PUT /predictions/me` valida y responde `400 BusinessRuleError` si esta bloqueado.
  - Frontend: cuando `locked=true`, banner amber, boton "Guardar" oculto, `<fieldset disabled>` en cascada (selects + drag desactivados via `useDraggable({disabled})`).
  - Admin NO puede sobreescribir tras el deadline (decision consciente).
- **TZ-naive fix** (commit `150b41b`): `TournamentPrediction.updated_at` es `timestamp without time zone` en BD; cambiado a `datetime.now(UTC).replace(tzinfo=None)` para evitar `can't subtract offset-naive and offset-aware datetimes` de asyncpg.
- **Audit `is_active`** (commits `e410482` + `d934346`): el filtro `SeasonParticipant.is_active.is_(True)` ahora se aplica en TODOS los listados publicos: standings general, balances economicos, listado de plantillas, draft participants, evolution chart y rankings para evaluar logros. **No filtran** (intencionalmente): detalles historicos de jornadas (muestran quien jugo entonces aunque ahora este inactivo), listados de admin para activar/desactivar.
- **Estado**: [x] Completado (2026-05-22).

---

## Resumen

| # | Mejora | Impacto | Complejidad | Estado |
|---|--------|---------|-------------|--------|
| 1.1 | Countdown deadline | Alto | Baja | Completado |
| 1.2 | Historial alineaciones | Alto | Baja | Completado |
| 1.3 | Estadisticas publicas | Alto | Baja | Pendiente |
| 1.4 | Notificaciones deadline | Alto | Media-Alta | Completado |
| 1.5 | Desglose puntos jornada | Alto | Baja | Completado |
| 2.1 | Comparador H2H | Medio | Media | Pendiente |
| 2.2 | MVP por jornada | Medio | Baja | Completado |
| 2.3 | Evolucion personal | Medio | Media | Completado |
| 2.4 | Plantillas mejoradas | Medio | Media | Pendiente |
| 3.1 | Logros/badges | Medio | Alta | Completado |
| 3.2 | Draft en vivo | Bajo | Alta | Completado |
| 3.3 | Predicciones | Medio | Alta | Completado |
| 4.1 | PWA | Medio | Baja | Completado |
| 4.2 | Lazy loading | Bajo | Media | Pendiente |
| 2.5 | Acierto de Mister | Alto | Alta | Completado |
| 2.6 | Info enriquecida alineacion | Alto | Media | Completado |
| 4.3 | Tests | Alto (tecnico) | Alta | Pendiente |
| 4.4 | Sesion unica | Alto (seguridad) | Media | Completado |
| 4.5 | Ciclo vida temporada | Alto (operativo) | Media | Completado |
| 4.6 | Palmares historico | Medio | Media | Completado |
| 4.7 | Grupos participantes | Alto | Media | Completado |
| 5.1 | Infraestructura torneos | Alto | Alta | Completado |
| 5.2 | Grupos/Cuadro/Predicciones torneo | Alto | Alta | Completado |
| 5.3 | Auto-scoring predicciones | Alto | Media | Completado |
| 5.4 | Banderas + DnD predicciones | Alto | Media | Completado |
| 5.5 | Predicciones publica/privada + lock + audit is_active | Alto | Media | Completado |

## Criterios de validacion

Cada mejora implementada debe:
1. Pasar lint + typecheck (backend: ruff + mypy, frontend: eslint + tsc)
2. Funcionar en mobile y desktop
3. Respetar reglas de negocio (`matchdays.counts` + `matches.counts`)
4. No exponer datos sensibles a usuarios no-admin
5. Desplegarse con el comando estandar de produccion
