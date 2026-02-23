# Liga VPV Fantasy — Contexto del Proyecto

## 🎯 Qué es

Aplicación web (ligavpv.com) para gestionar una liga fantasy de fútbol entre amigos basada en La Liga española. Actualmente funciona con frontend Polymer (obsoleto) y scraping Python. Se reconstruye desde cero.

---

## 🏗️ Stack Tecnológico (Decisiones cerradas)

| Capa | Tecnología | Notas |
|------|-----------|-------|
| **Frontend** | Next.js + Tailwind CSS | Frontend puro, consume API REST. No tiene lógica de negocio. |
| **Backend/API** | FastAPI (Python) | API única para TODA la lógica de negocio + scraping. SQLAlchemy como ORM. |
| **Base de datos** | PostgreSQL | En servidor dedicado. Migración desde MySQL actual con pgloader. |
| **Autenticación** | NextAuth.js | Contra la BD PostgreSQL. |
| **Notificaciones** | Bot Telegram (python-telegram-bot) | Envío de imágenes de alineación. Ya existe, se mantiene. |
| **Hosting** | Servidor dedicado AlmaLinux 10 | Coste: 0€ |
| **Fotos jugadores** | Disco local + Nginx estáticos | WebP 200x200, path en BD. Pillow para conversión en scraping. |

### Arquitectura

```
[Nginx :443]
  ├── /            → Next.js (PM2, puerto 3000)
  ├── /api/*       → FastAPI (uvicorn, puerto 8000)
  └── /static/*    → Archivos estáticos (fotos jugadores, imágenes alineaciones)

[PostgreSQL :5432]  ← conexión local
[Cron]              → scraping por jornada
[Telegram Bot]      → envío alineaciones
```

### Estrategia de migración

```
FASE 1: [Next.js frontend] → [FastAPI API] → [MySQL existente]
FASE 2: [Next.js frontend] → [FastAPI API] → [PostgreSQL nuevo]
         (frontend no se toca, solo cambia connection string en FastAPI)
```

### Estructura de archivos estáticos

```
/var/www/ligavpv/static/
  └── players/
      ├── 2025-26/
      │   ├── player_123.webp
      │   └── ...
      └── 2024-25/
          └── ...
```

Nginx config:
```nginx
location /static/ {
    alias /var/www/ligavpv/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

---

## 👥 Roles y Acceso

### Público (sin login)
- Clasificación general
- Jornadas: puntuaciones, desglose por jugador
- Plantillas de todos los participantes
- Historial de drafts (orden de elección)
- Balance económico global

### Participante (con login — usuario/contraseña)
- Alinear jornada (montar 11, confirmar con contraseña → imagen → Telegram)
- Mi balance personal
- Participar en draft en vivo

### Admin (con login)
- Gestión temporada: crear, configurar jornadas, reglas de puntuación, reglas económicas
- Gestión participantes: alta/baja, credenciales
- Scraping: lanzar carga de jugadores/equipos, puntuaciones post-jornada
- Drafts: sortear orden, abrir draft (vivo o registro manual), draft invierno
- Gestión jornadas: marcar computa/no computa, partidos aplazados
- Gestión pagos: balance global, liquidación final

---

## 🔄 Flujos de Negocio

### Pre-temporada (Admin)
1. Crear temporada: jornada inicio/fin, nº jugadores draft (26 por defecto), minutos deadline alineación
2. Configurar reglas de puntuación (configurables por temporada en BD)
3. Configurar reglas económicas (cuota inicial, pagos semanales por puesto, coste cambios draft invierno, premios finales)
4. Scraping futbolfantasy.com → cargar jugadores, equipos, fotos (WebP 200x200)
5. Alta participantes + credenciales
6. Sortear orden draft
7. Ejecutar draft serpiente (soporta modo en vivo por app O registro manual posterior)

### Jornada a jornada
8. Participante monta su 11 validando formaciones permitidas
9. Fecha límite: X minutos antes del primer partido de la jornada (configurable)
10. Confirmación con contraseña → genera imagen → envío automático Telegram
11. Scraping post-partidos para estadísticas y puntuaciones
12. Admin marca si jornada computa o no
13. **Partidos individuales pueden no computar** (aplazados) aunque la jornada sí compute
14. Cálculo puntos con fórmula propia (NO la de futbolfantasy.com)
15. Cálculo pago semanal según puesto en la jornada

### Draft invierno
16. Admin abre ventana de draft invierno
17. Participantes descartan jugadores que no quieren
18. Pago por cada cambio realizado
19. Draft lineal (NO serpiente)
20. Continúa temporada con plantillas actualizadas

### Fin de temporada
21. Reparto premios según clasificación final
22. Balance: pagado vs recibido por participante

### Competiciones futuras (NO implementar ahora, solo preparar BD)
- 2 playoffs
- Competición de copa
- La tabla `competitions` existe en el modelo pero no se implementa

---

## ⚽ Formaciones Válidas

| Formación | DEF | MED | DEL |
|-----------|-----|-----|-----|
| 1-3-4-3 | 3 | 4 | 3 |
| 1-3-5-2 | 3 | 5 | 2 |
| 1-4-4-2 | 4 | 4 | 2 |
| 1-4-3-3 | 4 | 3 | 3 |
| 1-5-4-1 | 5 | 4 | 1 |
| 1-5-3-2 | 5 | 3 | 2 |

Siempre 1 POR + 10 jugadores de campo. Validación en tabla `valid_formations`.

---

## 📊 Sistema de Puntuación (Fórmula propia, configurable por temporada)

Las reglas se almacenan en la tabla `scoring_rules` y se pueden modificar entre temporadas sin tocar código.

### Participación
- Jugar el partido: +1 punto
- Titular (inicia o juega 90 min completos): +1 punto
  - Suplente que entra (evento "Entrada"): NO recibe punto de titular
  - Titular sustituido (evento "Salida"): SÍ recibe punto de titular

### Resultado del equipo
- Victoria: +2 | Empate: +1 | Derrota: 0

### Goles (depende de posición)
- POR: +10 | DEF: +8 | MED: +7 | DEL: +5

### Imbatibilidad (portería a cero)
- **POR**: 0 goles encajados Y ≥65 min jugados → +4 pts. 1 gol → 0 pts. >1 gol → penalización = -nº goles encajados
- **DEF**: 0 goles encajados Y ≥45 min jugados → +3 pts. Con goles → 0 pts (sin penalización)
- **MED/DEL**: no aplica

### Acciones positivas
- Gol de penalti: +5 | Asistencia: +2 | Penalti parado (POR): +5
- Tiro al palo: +1 | Penalti forzado: +1

### Acciones negativas
- Penalti fallado: -3 | Gol en propia meta: -2 | Amarilla: -1
- Doble amarilla: -3 | Roja directa: -3 | Penalti cometido: -1
- Amarilla quitada por comité: se registra, NO afecta puntuación

### Valoración mediática
- **Marca** (estrellas): ⭐=+1, ⭐⭐=+2, ⭐⭐⭐=+3, ⭐⭐⭐⭐=+4, "-"=-1, "SC"=0
- **AS** (picas): cada pica=+1, "-"=-1, "SC"=0

### Fórmula total jornada
```
pts_total = pts_play + pts_starter + pts_result + pts_clean_sheet
          + pts_goals + pts_penalty_goals + pts_assists + pts_penalties_saved
          + pts_woodwork + pts_penalties_won
          + pts_penalties_missed + pts_own_goals + pts_yellow + pts_red + pts_pen_committed
          + pts_marca + pts_as
```

---

## 🗃️ Modelo de Datos PostgreSQL (18 tablas)

> El modelo completo con SQL está en `modelo_datos_vpv.md`. Aquí el resumen ejecutivo.

### Tablas principales

| # | Tabla | Propósito |
|---|---|---|
| 1 | `users` | Identidad única (username, password_hash, display_name, is_admin, telegram_chat_id) |
| 2 | `seasons` | Configuración por temporada (jornadas, deadline, estado, draft_pool_size) |
| 3 | `scoring_rules` | Reglas de puntuación configurables por temporada y posición |
| 4 | `season_payments` | Configuración económica (cuota, pagos semanales por puesto, premios) |
| 5 | `season_participants` | Vincula usuario ↔ temporada (draft_order, is_active) |
| 6 | `teams` | Equipos por temporada (soporta ascensos/descensos) |
| 7 | `players` | Jugadores por temporada (equipo, posición, foto, owner_id → quién lo tiene) |
| 8 | `drafts` | Eventos de draft (snake/linear, preseason/winter, estado) |
| 9 | `draft_picks` | Cada elección del draft (round, pick_number, jugador, participante) |
| 10 | `matchdays` | Jornadas (número, estado, counts=TRUE/FALSE, deadline, stats_ok) |
| 11 | `matches` | Partidos (local, visitante, resultado, counts=TRUE/FALSE, stats_ok) |
| 12 | `player_stats` | Stats scraping + puntos calculados por jugador×jornada |
| 13 | `lineups` | Alineación del participante por jornada (formación, confirmed, telegram_sent) |
| 14 | `lineup_players` | Los 11 jugadores alineados (posición, orden, puntos) |
| 15 | `participant_matchday_scores` | Puntuación total del participante por jornada + ranking |
| 16 | `transactions` | Movimientos económicos (initial_fee, weekly_payment, winter_draft_fee, prize) |
| 17 | `competitions` | Futuro: playoffs, copa (solo estructura, no implementar) |
| 18 | `valid_formations` | Formaciones permitidas (datos fijos) |

### Relaciones clave

```
users ──< season_participants >── seasons
season_participants ──< draft_picks >── drafts >── seasons
season_participants ──< lineups >── matchdays >── seasons
players ──< player_stats >── matchdays
players >── teams >── seasons
players.owner_id ──> season_participants
lineups ──< lineup_players >── players
matchdays ──< matches
```

### Mapeo MySQL actual → PostgreSQL

| MySQL | PostgreSQL |
|---|---|
| `temporadas` | `seasons` + `scoring_rules` + `season_payments` |
| `usuarios_temp` (duplicado por temporada) | `users` + `season_participants` |
| `equipos` (sin temporada) | `teams` (vinculado a temporada) |
| `jornadas_temp` (mega-tabla 55+ cols) | `player_stats` + `lineups` + `lineup_players` |
| `alineaciones_temp` (todos con flag alineado) | `lineups` + `lineup_players` (solo los 11) |
| `list_jornadas_temp` (jornada = partido) | `matchdays` + `matches` (separados) |
| `vpv_audit` | Innecesario |
| *(no existía)* | `drafts`, `draft_picks`, `transactions`, `competitions`, `scoring_rules`, `valid_formations` |

### Campos de player_stats (scraping → cálculo)

**Datos crudos del scraping:**
- `played`, `event` (Entrada/Salida), `event_minute`, `minutes_played`
- `home_score`, `away_score`, `result` (0/1/2), `goals_for`, `goals_against`
- `goals`, `penalty_goals`, `penalties_missed`, `own_goals`, `assists`, `penalties_saved`
- `yellow_card`, `yellow_removed`, `double_yellow`, `red_card`
- `woodwork`, `penalties_won`, `penalties_committed`
- `marca_rating` ("1"-"4", "-", "SC"), `as_picas` ("0"-"3", "-", "SC")

**Puntos calculados (usando scoring_rules de la temporada):**
- `pts_play`, `pts_starter`, `pts_result`, `pts_clean_sheet`
- `pts_goals`, `pts_penalty_goals`, `pts_assists`, `pts_penalties_saved`
- `pts_woodwork`, `pts_penalties_won`
- `pts_penalties_missed`, `pts_own_goals`, `pts_yellow`, `pts_red`, `pts_pen_committed`
- `pts_marca`, `pts_as`, `pts_marca_as`, `pts_total`

---

## 💰 Sistema Económico

Configurable por temporada en tabla `season_payments`:

| Tipo | Ejemplo |
|---|---|
| `initial_fee` | Cuota inicial: 50€ |
| `weekly_position` | Puesto 7º: 3€, Puesto 8º (último): 5€ |
| `winter_draft_change` | 2€ por cada cambio en draft invierno |
| `prize` | 1º: 200€, 2º: 100€, 3º: 50€ |

Las transacciones se registran en tabla `transactions` (positivo = debe pagar, negativo = recibe).

---

## 🖥️ Mapa de Pantallas

### Público (sin login)
- **Home**: pendiente de definir
- **Clasificación general**
- **Jornadas**: puntuaciones por participante, desglose por jugador
- **Plantillas**: de todos los participantes (26 jugadores con foto, equipo, posición, puntos)
- **Historial drafts**: orden de elección de cada draft
- **Balance económico global**

### Participante (requiere login)
- **Dashboard**: clasificación, próxima jornada, última puntuación, balance
- **Mi plantilla**: 26 jugadores con foto, equipo, posición, puntos acumulados
- **Alinear jornada**: seleccionar 11, elegir formación válida, vista previa imagen, confirmar con contraseña → envío Telegram
- **Mi balance**: cuota, pagos semanales, costes draft invierno, total

### Admin (requiere login admin)
- **Gestión temporada**: crear, configurar jornadas, reglas puntuación, reglas económicas
- **Gestión participantes**: alta/baja, credenciales
- **Scraping**: lanzar carga jugadores/equipos, lanzar carga puntuaciones
- **Gestión drafts**: sortear orden, abrir draft (vivo/manual), draft invierno
- **Gestión jornadas**: marcar computa/no computa, partidos aplazados
- **Gestión pagos**: balance global, liquidación final

---

## 📝 Reglas de Negocio Importantes

1. **Partidos que no computan**: a dos niveles. `matchdays.counts` para jornada entera, `matches.counts` para partido individual. Al calcular puntuación del participante, solo suman pts_total de jugadores cuyo match tiene `counts = TRUE`.

2. **Titular vs suplente**: evento "Salida" = era titular (recibe punto). Evento "Entrada" = era suplente (no recibe punto de titular). Sin evento = titular que jugó 90 min.

3. **Imbatibilidad portero**: si encaja >1 gol, la penalización es exactamente el número de goles encajados (3 goles = -3 pts). Si encaja exactamente 1 gol = 0 pts (sin penalización ni bonus).

4. **Draft serpiente**: Ronda 1 (1→8), Ronda 2 (8→1), Ronda 3 (1→8)... hasta completar 26 jugadores por participante.

5. **Draft invierno**: lineal (no serpiente). Se paga por cada cambio.

6. **Deadline alineación**: X minutos antes del primer partido de la jornada. Configurable en `seasons.lineup_deadline_min`.

7. **Scoring rules configurables**: si la próxima temporada cambian valores (ej: gol delantero = 6 en vez de 5), se modifica en `scoring_rules` sin tocar código. Para copiar reglas: `INSERT INTO scoring_rules ... SELECT ... FROM scoring_rules WHERE season_id = :old`.

8. **Marcador completitud**: un partido se marca como `stats_ok = TRUE` cuando tiene menos de 12 valores "SC" en las valoraciones mediáticas.

9. **Cambio de posición**: un jugador puede cambiar de posición durante el draft de invierno. La posición afecta directamente la puntuación (goles, imbatibilidad). Por tanto:
   - `players.position` = posición **actual** del jugador (al final de la temporada o tras el draft invierno).
   - `player_stats.position` = posición **en esa jornada concreta** (fuente de verdad para el cálculo de puntos).
   - La puntuación se calcula siempre usando `player_stats.position`, nunca `players.position`.

10. **Cambio de equipo**: un jugador puede cambiar de equipo en cualquier momento de la temporada (mercado de invierno, etc.). Por tanto:
    - `players.team_id` = equipo **actual** del jugador.
    - El equipo real en cada jornada se infiere desde `player_stats.match_id` → `matches` (equipo local o visitante según corresponda).
    - El scraping actualiza `players.team_id` al cargar cada jornada.

---

## 📁 Archivos de Referencia del Proyecto

- `normas_puntuacion_vpv.md` — Documento detallado con todas las reglas de puntuación
- `modelo_datos_vpv.md` — Modelo de datos PostgreSQL completo con SQL, diagrama y consultas ejemplo
- `dump-ligavpv-202602191638.sql` — Esquema MySQL actual (6 tablas) para referencia de migración
