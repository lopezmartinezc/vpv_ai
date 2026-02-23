# CLAUDE.md — Liga VPV Fantasy

## Que es
Aplicacion web (ligavpv.com) para gestionar una liga fantasy de futbol entre amigos basada en La Liga espanola. Reconstruccion completa desde Polymer+MySQL obsoleto.

## Architecture: Scope Rule
- **Global**: Used by 2+ features -> src/global/ or src/shared/
- **Local**: Used by 1 feature only -> src/features/[feature-name]/
- Services at root must be singleton
- Names must scream functionality

## Tech Stack
- Frontend: Next.js + Tailwind CSS (TypeScript) — frontend puro, consume API REST
- Backend: Python + FastAPI + SQLAlchemy — API unica para TODA la logica de negocio + scraping
- Database: PostgreSQL (migracion desde MySQL actual)
- ORM: SQLAlchemy 2.0+ async (asyncpg)
- Auth: NextAuth.js (frontend) + JWT validado en FastAPI (backend)
- Notificaciones: Bot Telegram (python-telegram-bot)
- Hosting: Servidor dedicado AlmaLinux 10 (Nginx + PM2 + uvicorn)
- Frontend Testing: Vitest + React Testing Library + Playwright
- Backend Testing: pytest + httpx + TestContainers

## Arquitectura de Despliegue
```
[Nginx :443]
  |- /            -> Next.js (PM2, puerto 3000)
  |- /api/*       -> FastAPI (uvicorn, puerto 8000)
  \- /static/*    -> Archivos estaticos (fotos jugadores WebP 200x200)

[PostgreSQL :5432]  <- conexion local
[Cron]              -> scraping por jornada
[Telegram Bot]      -> envio alineaciones
```

## Modelo de Datos (18 tablas PostgreSQL)
Referencia completa: `claude_data/modelo_datos_vpv.md`

Tablas: users, seasons, scoring_rules, season_payments, season_participants, teams, players, drafts, draft_picks, matchdays, matches, player_stats, lineups, lineup_players, participant_matchday_scores, transactions, competitions (futuro), valid_formations.

## Reglas de Negocio Clave
Referencia completa: `claude_data/normas_puntuacion_vpv.md`

1. Puntuacion configurable por temporada (tabla scoring_rules) — NO hardcodear valores
2. Partidos que no computan: a 2 niveles (matchdays.counts + matches.counts)
3. player_stats.position es la fuente de verdad para calculo de puntos (no players.position)
4. Draft serpiente para pretemporada, lineal para invierno
5. Deadline alineacion: seasons.lineup_deadline_min minutos antes del primer partido
6. Alineacion: 1 POR + 10 de campo, formaciones en tabla valid_formations

## Estrategia de Migracion
FASE 1: Next.js -> FastAPI -> MySQL existente
FASE 2: Next.js -> FastAPI -> PostgreSQL (solo cambia connection string)

## Memory Protocol (Engram)
- START of session: Always `mem_context` to recover state
- END of session: Always `mem_session_summary`
- After significant decisions: `mem_save` with type and structured content
- After bugfixes: `mem_save` with What/Why/Where/Learned format

## SDD Workflow (for non-trivial tasks)
1. EXPLORE -> analyze codebase + recover Engram context
2. PROPOSE -> proposal (WHY/SCOPE/APPROACH) -> ask for approval
3. SPEC + DESIGN -> delegate to architect/api-designer -> ask for approval
4. TDD RED -> qa-tdd-engineer writes failing tests
5. TDD GREEN -> implementers make tests pass
6. VALIDATE -> quality-auditor + security-engineer
7. DELIVER -> devops-cloud-engineer -> pipeline + docs

## Git Strategy (NO AI mentions in commits)
- Architecture: "feat: add [feature] architecture"
- Tests: "test: add [feature] tests (RED)"
- Implementation: "feat: implement [feature] (GREEN)"
- Security: "fix(security): [description]"
- Accessibility: "feat(a11y): [description]"
- Docs: "docs: [description]"
- Refactor: "refactor: [description]"

## Rules
- NEVER write code without concrete acceptance criteria
- NEVER implement without failing tests first (TDD)
- NEVER mention Claude or AI in commits
- NEVER hardcode scoring values — always read from scoring_rules table
- ALWAYS validate with quality-auditor before merge to main
- ALWAYS run security-engineer audit when touching auth/crypto/PII
- ALWAYS use player_stats.position (not players.position) for scoring calculations
- ALWAYS check matchdays.counts AND matches.counts when computing standings
