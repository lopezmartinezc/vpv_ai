# Liga VPV Fantasy

Aplicacion web para gestionar una liga fantasy de futbol entre amigos basada en La Liga espanola. Reconstruccion completa desde Polymer+MySQL hacia Next.js+FastAPI+PostgreSQL.

**URL**: [ligavpv.com](https://ligavpv.com)

## Stack

| Capa | Tecnologia |
|------|------------|
| Frontend | Next.js 16 + React 19 + Tailwind CSS v4 + TypeScript |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 async (asyncpg) |
| Base de datos | PostgreSQL 16 |
| Auth | JWT (HS256) — login via FastAPI, token en localStorage |
| Scraping | BeautifulSoup + httpx + APScheduler (futbolfantasy.com) |
| Notificaciones | Telegram bot (python-telegram-bot) |

## Arquitectura

```
[Nginx :443]
  |- /            -> Next.js (PM2, puerto 3000)
  |- /api/*       -> FastAPI (uvicorn, puerto 8000)
  \- /static/*    -> Archivos estaticos (fotos jugadores WebP 200x200)

[PostgreSQL :5432]  <- conexion local
[APScheduler]       -> scraping automatico + sync calendario diario
[Telegram Bot]      -> envio alineaciones
```

## Inicio rapido

### Con Docker (recomendado)

```bash
git clone <repo-url> && cd vpv_ai
cp .env.example .env          # editar si es necesario
docker compose up --build
```

Servicios disponibles:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/api
- Swagger docs: http://localhost:8001/api/docs (solo en modo debug)
- PostgreSQL: localhost:5433

### Sin Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # configurar DATABASE_URL, JWT_SECRET_KEY
uvicorn src.app:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.local.example .env.local  # configurar NEXT_PUBLIC_API_URL
npm run dev
```

## Estructura del proyecto

```
vpv_ai/
  backend/
    src/
      app.py                    # FastAPI app + lifespan (scheduler start/stop)
      core/
        config.py               # Settings (pydantic-settings, env vars)
        database.py             # AsyncEngine + AsyncSessionLocal
        exceptions.py           # VPVError hierarchy -> HTTP status mapping
        logging.py              # structlog setup
      shared/
        base/repository.py      # BaseRepository[T] generico
        dependencies.py         # get_db, get_current_user, get_current_admin
        models/                 # 11 SQLAlchemy models (18 tablas)
        schemas/common.py       # PaginatedResponse[T]
      features/
        auth/                   # Login, registro, invitaciones, gestion usuarios
        seasons/                # Temporadas, scoring rules, pagos, formaciones
        matchdays/              # Jornadas, partidos, alineaciones, puntuaciones
        standings/              # Clasificacion general (SQL aggregation)
        squads/                 # Plantillas de participantes
        drafts/                 # Drafts pretemporada e invierno
        economy/                # Economia: cuotas, pagos semanales, premios
        scraping/               # Scraping futbolfantasy.com + scheduler
        health/                 # Health check endpoint
    tests/                      # pytest + httpx
    static/                     # Fotos jugadores (WebP 200x200)

  frontend/
    src/
      app/                      # Next.js App Router pages
        page.tsx                # Dashboard home
        login/                  # Login
        registro/[token]/       # Registro via invitacion
        clasificacion/          # Standings
        jornadas/               # Matchdays + detail + lineup
        plantillas/             # Squads
        drafts/                 # Draft picks
        economia/               # Economy
        admin/                  # Panel admin (6 secciones)
          layout.tsx            # Tab nav admin
          usuarios/             # Gestion usuarios
          invitaciones/         # Invitaciones
          scraping/             # Control scheduler + scraping manual
          temporadas/           # Config temporada + scoring rules
          jornadas/             # Toggle counts jornadas/partidos
          economia/             # Transacciones manuales
      components/
        layout/                 # AppShell, NavBar, BottomNav, SeasonSelector
        dashboard/              # MatchdayAccordion, Podium, QuickStats, NavCards
        matchdays/              # MatchList, ScoreList, PlayerList
        standings/              # StandingsList
        drafts/                 # PicksList
        economy/                # BalanceList, TransactionList
        ui/                     # PlayerAvatar, ThemeToggle, NavIcon, Skeleton
      contexts/                 # AuthContext, SeasonContext, ThemeContext
      hooks/                    # useFetch, useDashboardData
      lib/
        api-client.ts           # HTTP client con JWT auto-inject
        auth.ts                 # NextAuth config (scaffolded)

  migration/
    docker-compose.yml          # MySQL 5.7 (3307) + PG 16 (5432)
    schema/
      00_create_schema.sql      # DDL completo (18 tablas)
      01_seed_data.sql          # Datos de referencia
      02_dev_seed.sql           # Seed desarrollo
    scripts/
      migrate.py                # Orquestador (step_01 a step_10)
      step_01_seasons.py        # ... a step_10_validate.py
```

## Modelo de datos

18 tablas PostgreSQL. Referencia completa en [claude_data/modelo_datos_vpv.md](claude_data/modelo_datos_vpv.md).

Tablas principales:
- `users` — Usuarios (15)
- `seasons` — Temporadas (8)
- `teams` — Equipos por temporada
- `players` — Jugadores por temporada (6,344)
- `matchdays` — Jornadas (38 por temporada)
- `matches` — Partidos reales La Liga (10 por jornada)
- `player_stats` — Estadisticas por jugador/jornada (224,609)
- `lineups` / `lineup_players` — Alineaciones fantasy
- `participant_matchday_scores` — Puntuaciones calculadas
- `scoring_rules` — Reglas de puntuacion configurables por temporada
- `transactions` — Economia (cuotas, pagos, premios)
- `drafts` / `draft_picks` — Drafts pretemporada/invierno

## Reglas de negocio clave

1. **Puntuacion configurable** por temporada (tabla `scoring_rules`) — nunca hardcodeada
2. **Partidos que no computan** a 2 niveles: `matchdays.counts` + `matches.counts`
3. **`player_stats.position`** es la fuente de verdad para calcular puntos (no `players.position`)
4. **Draft serpiente** para pretemporada, **lineal** para invierno
5. **Deadline alineacion**: `seasons.lineup_deadline_min` minutos antes del primer partido
6. **Alineacion**: 1 POR + 10 de campo, formaciones en tabla `valid_formations`

## API

42 endpoints REST. Documentacion completa en [docs/API.md](docs/API.md).

Resumen por feature:

| Feature | Endpoints | Auth |
|---------|-----------|------|
| Health | 1 GET | Publico |
| Auth | 12 (login, registro, invites, admin users) | Mixto |
| Seasons | 8 (CRUD + scoring rules) | Publico + Admin |
| Matchdays | 5 (list, detail, lineup, admin update) | Publico + Admin |
| Standings | 1 GET | Publico |
| Squads | 2 GET | Publico |
| Drafts | 2 GET | Publico |
| Economy | 4 (balances, transactions, admin CRUD) | Publico + Admin |
| Scraping | 8 (scrape, calendar, scheduler control) | Mixto |

## Scraping

Sistema automatico que obtiene datos de futbolfantasy.com. Documentacion completa en [docs/SCRAPING.md](docs/SCRAPING.md).

- **Scheduler**: APScheduler con 2 jobs — tick cada 15 min (CRC change detection) + calendar sync diario 06:00 UTC
- **Fuente**: futbolfantasy.com (unica fuente — no Marca/As directamente)
- **Datos**: resultados partidos, estadisticas jugadores, calendario con fechas

## Configuracion

Variables de entorno principales (ver `.env.example`):

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://vpv:vpv_secret@localhost:5432/ligavpv` |
| `JWT_SECRET_KEY` | Secreto para firmar JWT tokens | `CHANGE-ME-IN-PRODUCTION` |
| `CORS_ORIGINS` | Origenes CORS permitidos (JSON array) | `["http://localhost:3000"]` |
| `DEBUG` | Habilitar Swagger docs y logs debug | `false` |
| `NEXT_PUBLIC_API_URL` | URL base del API (frontend) | `http://localhost:8000/api` |
| `SCRAPING_POLL_INTERVAL_SECONDS` | Intervalo entre ticks del scheduler | `900` (15 min) |

## Scripts utiles

```bash
# Backend — lint + type check
cd backend && ruff check src/ && mypy src/

# Frontend — lint + type check
cd frontend && npm run lint && npm run type-check

# Scraping CLI
cd backend
python -m src.features.scraping.cli scrape-current          # Scrape jornada actual
python -m src.features.scraping.cli update-calendar 8       # Actualizar calendario temporada 8
python -m src.features.scraping.cli scrape-matchday 8 25    # Scrape J25 de temporada 8
python -m src.features.scraping.cli download-photos 8       # Descargar fotos jugadores

# Migracion MySQL -> PostgreSQL (una vez)
cd migration && python scripts/migrate.py
```

## Migracion

Completada. MySQL 5.7 (6 tablas, 52MB) -> PostgreSQL 16 (18 tablas normalizadas).

- 224,609 player_stats
- 3,039 matches
- 6,344 players
- 15 users
- 8 seasons

Scripts en `migration/scripts/` (step_01 a step_10 + `migrate.py` orquestador).
