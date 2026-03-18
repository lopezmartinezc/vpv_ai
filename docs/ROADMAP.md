# Roadmap de Mejoras — Liga VPV Fantasy

**Fecha**: 2026-03-18
**Estado**: En progreso

## Estado actual

La app esta en produccion (new.ligavpv.com) con todas las funcionalidades core:
- 30 paginas frontend (Next.js + Tailwind)
- 16 modulos backend (FastAPI + SQLAlchemy)
- 22 tablas PostgreSQL (+ achievement_definitions, achievements)
- Liga, Copa, Drafts, Alineaciones, Economia, Scraping automatico, Admin completo

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
- **Solucion**: Listar alineaciones por jornada con formacion, jugadores y puntos
- **Backend**: `GET /lineups/{season_id}/history` (datos en `lineups` + `lineup_players`)
- **Frontend**: tabla/cards en `/perfil` o seccion dedicada
- **Complejidad**: Baja
- **Estado**: [ ] Pendiente

### 1.3 Estadisticas publicas (no solo admin)
- **Problema**: `/admin/estadisticas` solo accesible para admin
- **Solucion**: Crear `/estadisticas` publico con tabs Jugadores y Liga
- **Backend**: endpoints `/stats/{season_id}/players` y `/stats/{season_id}/league` ya no requieren auth
- **Frontend**: nueva pagina reutilizando componentes existentes
- **Complejidad**: Baja
- **Estado**: [ ] Pendiente

### 1.4 Notificaciones Telegram automaticas
- **Problema**: Notificaciones Telegram son manuales (admin pulsa boton)
- **Solucion**: Scheduler job que envie recordatorio X horas antes del deadline a usuarios sin alineacion. Notificar cuando se publican puntos
- **Backend**: nuevo job en `scheduler.py` usando servicio Telegram existente
- **Complejidad**: Media
- **Estado**: [ ] Pendiente

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
- **Solucion**: WebSocket para picks en vivo, countdown por turno
- **Nota**: Bajo impacto relativo (se usa 2 veces al ano)
- **Complejidad**: Alta
- **Estado**: [ ] Pendiente

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

---

## Resumen

| # | Mejora | Impacto | Complejidad | Estado |
|---|--------|---------|-------------|--------|
| 1.1 | Countdown deadline | Alto | Baja | Completado |
| 1.2 | Historial alineaciones | Alto | Baja | Pendiente |
| 1.3 | Estadisticas publicas | Alto | Baja | Pendiente |
| 1.4 | Telegram automatico | Alto | Media | Pendiente |
| 1.5 | Desglose puntos jornada | Alto | Baja | Completado |
| 2.1 | Comparador H2H | Medio | Media | Pendiente |
| 2.2 | MVP por jornada | Medio | Baja | Completado |
| 2.3 | Evolucion personal | Medio | Media | Completado |
| 2.4 | Plantillas mejoradas | Medio | Media | Pendiente |
| 3.1 | Logros/badges | Medio | Alta | Completado |
| 3.2 | Draft en vivo | Bajo | Alta | Pendiente |
| 3.3 | Predicciones | Medio | Alta | Completado |
| 4.1 | PWA | Medio | Baja | Completado |
| 4.2 | Lazy loading | Bajo | Media | Pendiente |
| 4.3 | Tests | Alto (tecnico) | Alta | Pendiente |
| 4.4 | Sesion unica | Alto (seguridad) | Media | Completado |

## Criterios de validacion

Cada mejora implementada debe:
1. Pasar lint + typecheck (backend: ruff + mypy, frontend: eslint + tsc)
2. Funcionar en mobile y desktop
3. Respetar reglas de negocio (`matchdays.counts` + `matches.counts`)
4. No exponer datos sensibles a usuarios no-admin
5. Desplegarse con el comando estandar de produccion
