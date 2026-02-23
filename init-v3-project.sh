#!/bin/bash
# ============================================================================
# init-v3-project.sh — Project Init: Liga VPV Fantasy (Agent System v3)
# ============================================================================
# Ejecutar en la RAÍZ del proyecto vpv_ai. Genera:
#   - CLAUDE.md (configuración del proyecto con contexto VPV)
#   - AGENTS.md (reglas para GGA quality gate)
#   - .gga (configuración de GGA)
#   - .claude/skills/ (skills específicos: Next.js, FastAPI, SQLAlchemy, VPV domain)
#
# Stack pre-configurado:
#   Frontend:  Next.js + Tailwind CSS (TypeScript)
#   Backend:   FastAPI (Python) + SQLAlchemy
#   Database:  PostgreSQL
#   Auth:      NextAuth.js
#   Hosting:   Servidor dedicado AlmaLinux 10 + Nginx + PM2 + uvicorn
#
# Uso: chmod +x init-v3-project.sh && ./init-v3-project.sh
# ============================================================================

set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

PROJECT_DIR="$(pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  ⚽ Liga VPV Fantasy — Agent System v3 Init${NC}"
echo -e "${BLUE}  Project: ${PROJECT_NAME}${NC}"
echo -e "${BLUE}  Path:    ${PROJECT_DIR}${NC}"
echo -e "${BLUE}  Stack:   Next.js + FastAPI + PostgreSQL + SQLAlchemy${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ─── Verificar agentes globales ─────────────────────────────────────────────
if [ ! -d "$HOME/.claude/agents" ] || [ -z "$(ls -A $HOME/.claude/agents 2>/dev/null)" ]; then
  echo -e "\n${RED}No global agents found in ~/.claude/agents/${NC}"
  echo -e "   Run ${BOLD}./install-v3-global.sh${NC} first."
  exit 1
fi
AGENT_COUNT=$(ls -1 ~/.claude/agents/*.md 2>/dev/null | wc -l)
echo -e "\n  ${AGENT_COUNT} global agents detected"

# ============================================================================
# STEP 1: Create .claude/skills/
# ============================================================================
echo -e "\n${GREEN}[1/4]${NC} Generating architecture-specific skills..."
mkdir -p .claude/skills

# ─── TypeScript skill ─────────────────────────────────────────────────────
mkdir -p .claude/skills/typescript
cat > .claude/skills/typescript/SKILL.md << 'SKILL_EOF'
# TypeScript Patterns (Frontend — Next.js)

## Strict Mode Always
- strict: true in tsconfig.json
- No "any" ever — use "unknown" and narrow with type guards
- No type assertions (as) unless absolutely necessary
- Enable noUncheckedIndexedAccess, exactOptionalPropertyTypes

## Type Patterns
- Interfaces for object shapes, types for unions/intersections/mapped types
- const assertions for literal types: `as const`
- Discriminated unions for state machines: `type State = { status: 'loading' } | { status: 'success'; data: T }`
- Template literal types for string patterns
- Branded types for domain primitives: `type UserId = string & { __brand: 'UserId' }`
- Prefer `satisfies` over `as` for type-safe inference

## Function Patterns
- Explicit return types on ALL exported functions
- Use overloads for complex signatures
- Generic constraints with `extends`
- Infer when obvious (internal/private functions)

## Error Handling
- Result<T, E> pattern over try/catch for expected domain errors
- Custom error classes extending Error with discriminant `readonly _tag` field
- Never throw in pure utility functions — return Result or Option

## Imports
- Type-only imports: `import type { Foo } from './foo'`
- Barrel exports (index.ts) only at module/feature boundaries, never internal
- Path aliases: `@/features/`, `@/shared/`, `@/lib/`
SKILL_EOF
echo "  typescript/SKILL.md"

# ─── Git workflow skill ───────────────────────────────────────────────────
mkdir -p .claude/skills/git-workflow
cat > .claude/skills/git-workflow/SKILL.md << 'SKILL_EOF'
# Git Workflow Patterns

## Conventional Commits
Format: type(scope): description
Types: feat, fix, docs, style, refactor, test, chore, perf, ci, build

## Commit Rules
- Atomic: one logical change per commit
- NEVER mention Claude, AI, LLM, or Copilot in commits
- NEVER force-push to shared branches (main, develop, release/*)
- Squash merge for features, merge commit for releases

## Branch Naming
- feat/TICKET-123-short-description
- fix/TICKET-456-bug-name
- chore/update-dependencies
- release/v1.2.0

## SDD Commit Strategy
- Architecture decisions: "feat: add [feature] architecture"
- Tests before code: "test: add [feature] tests (RED)"
- Implementation: "feat: implement [feature] (GREEN)"
- Security fixes: "fix(security): [description]"
- Docs: "docs: add [feature] documentation"

## PR Rules
- Small and focused (<400 lines when possible)
- Template: what changed, why, how to test, screenshots if UI
- Always rebase on target before merge
- At least 1 approval required

## Tags & Releases
- Semantic: vMAJOR.MINOR.PATCH
- Automate with: semantic-release, changesets, or release-please
SKILL_EOF
echo "  git-workflow/SKILL.md"

# ─── Technical writing skill ──────────────────────────────────────────────
mkdir -p .claude/skills/technical-writing
cat > .claude/skills/technical-writing/SKILL.md << 'SKILL_EOF'
# Technical Writing Patterns

## README Structure
1. Project name + one-line description
2. Badges (CI, coverage, version)
3. Quick Start (3-5 steps max)
4. Prerequisites and Installation
5. Usage with copyable examples
6. Configuration reference
7. Architecture overview (Mermaid diagram)
8. Contributing guide
9. License

## ADR Format (Architecture Decision Records)
- Title: ADR-NNN: Short Decision Title
- Status: Proposed | Accepted | Deprecated | Superseded by ADR-NNN
- Context: What is the issue motivating this decision?
- Decision: What is the change being proposed?
- Consequences: What becomes easier? What becomes harder?

## CHANGELOG (Keep a Changelog)
Sections: Added, Changed, Deprecated, Removed, Fixed, Security

## Runbook Format
1. Service name, purpose, owner
2. Dependencies and contact points
3. Common issues -> step-by-step resolution
4. Escalation path
5. Monitoring dashboard links

## Rules
- Docs-as-code: versioned alongside source
- Every doc states its audience (dev / ops / PM / end user)
- Code examples must be copyable and actually work
- Mermaid diagrams for anything with >2 components
- Table of contents in docs >200 lines
SKILL_EOF
echo "  technical-writing/SKILL.md"

# ─── React 19 + Next.js skill ────────────────────────────────────────────
mkdir -p .claude/skills/react-nextjs
cat > .claude/skills/react-nextjs/SKILL.md << 'SKILL_EOF'
# React 19 + Next.js Patterns (Frontend VPV)

## Architecture
- Next.js App Router (app/) as default
- Server Components by default, 'use client' only for interactivity
- Route groups for layout organization: (public), (auth), (admin)
- Frontend puro: consume API REST de FastAPI, no tiene logica de negocio
- NextAuth.js para autenticacion contra PostgreSQL

## Component Rules
- React 19 functional components only
- React.use() for promises and context reading
- useActionState + useFormStatus for form handling (Server Actions)
- useOptimistic for optimistic UI updates
- Scope Rule: src/shared/ (2+ features) vs src/features/[name]/ (1 feature)
- Container component name = feature name

## Data Fetching
- Server Components: async/await directly (no useEffect for data)
- Client Components: TanStack Query for server state from FastAPI API
- Server Actions for mutations (forms, writes)
- Revalidation: revalidatePath() / revalidateTag() after mutations
- Loading UI: loading.tsx per route segment
- Error UI: error.tsx per route segment

## State Management
- URL state (searchParams) for shareable/bookmarkable state
- Zustand for global client state (minimal — most state is server)
- React Context only for theme/locale/auth provider
- No Redux — unnecessary with Server Components + TanStack Query

## File Naming
- Components: PascalCase.tsx (LoginForm.tsx)
- Hooks: use-kebab-case.ts (use-auth.ts)
- Server Actions: kebab-case.action.ts (login.action.ts)
- Types: kebab-case.types.ts
- Tests: kebab-case.test.tsx
- Route files: page.tsx, layout.tsx, loading.tsx, error.tsx, not-found.tsx

## Styling
- Tailwind CSS as primary
- CSS Modules for complex component-specific styles
- cn() utility (clsx + tailwind-merge) for conditional classes
- No inline styles except dynamic values

## Validation
- Zod for all schema validation (shared between client and server)
- Validate in Server Actions before DB operations
- Return typed errors from actions, never throw

## Testing
- Vitest + React Testing Library for components
- Test Server Components by testing their output
- MSW for API mocking in client component tests
- Playwright for E2E (test real user flows)

## Performance
- next/image for all images (auto optimization)
- next/font for font loading (no layout shift)
- Dynamic imports: next/dynamic for heavy client components
- Metadata API for SEO (generateMetadata)
- Streaming with Suspense boundaries for progressive loading

## Security
- Server Actions validate ALL input with Zod
- Use next-safe-action for type-safe server actions with middleware
- CSRF protection is automatic in Server Actions
- Environment variables: NEXT_PUBLIC_ prefix only for client-safe values
- Middleware (middleware.ts) for auth guards on route groups

## VPV-Specific Routes
- (public): clasificacion, jornadas, plantillas, historial-drafts, balance
- (auth): dashboard, mi-plantilla, alinear-jornada, mi-balance
- (admin): gestion-temporada, gestion-participantes, scraping, drafts, jornadas, pagos
SKILL_EOF
echo "  react-nextjs/SKILL.md"

# ─── Python + FastAPI skill ───────────────────────────────────────────────
mkdir -p .claude/skills/python-fastapi
cat > .claude/skills/python-fastapi/SKILL.md << 'SKILL_EOF'
# Python + FastAPI Patterns (Backend VPV)

## Architecture
- FastAPI with APIRouter per feature domain
- Dependency injection via Depends()
- Pydantic v2 models for all request/response schemas
- Repository pattern for data access
- Async by default (async def endpoints)
- API unica para TODA la logica de negocio + scraping

## Project Structure
```
src/features/[feature_name]/
├── __init__.py
├── router.py          # APIRouter with endpoint definitions
├── service.py         # Business logic (injected via Depends)
├── repository.py      # Data access (SQLAlchemy async sessions)
├── schemas.py         # Pydantic models (request/response)
├── models.py          # SQLAlchemy ORM models
├── dependencies.py    # Feature-specific Depends() factories
└── tests/
```

## VPV Feature Domains
- seasons: gestion temporadas, scoring_rules, season_payments
- users: identidad, autenticacion, participantes
- teams: equipos La Liga por temporada
- players: jugadores, asignacion owner, posiciones
- drafts: draft serpiente (preseason) + draft lineal (winter)
- matchdays: jornadas, partidos, estados (counts/stats_ok)
- stats: scraping futbolfantasy.com, calculo puntos con scoring_rules
- lineups: alineaciones participante, validacion formaciones, imagen Telegram
- standings: clasificacion general, puntuacion por jornada
- transactions: sistema economico (cuotas, pagos semanales, premios)
- scraping: carga jugadores/equipos/estadisticas desde futbolfantasy.com

## Validation
- Pydantic v2 for all input/output validation (automatic in FastAPI)
- Field validators with @field_validator
- model_validator for cross-field validation
- Custom types with Annotated[] for reusable constraints

## Error Handling
- Custom exception handlers registered with app.exception_handler()
- Domain exceptions: NotFoundError, ConflictError, ValidationError
- HTTPException only at router level, never in service/repository
- Structured response: {"detail": {"code": "", "message": "", "errors": []}}

## Dependency Injection
- Depends() for service -> repository -> session chain
- Background tasks via BackgroundTasks parameter
- Lifespan events for startup/shutdown (DB pool, cache)

## Auth
- OAuth2PasswordBearer + JWT (NextAuth.js en frontend, JWT validado en FastAPI)
- Depends(get_current_user) for protected endpoints
- Role-based: Depends(require_role("admin"))
- 3 niveles: publico (sin login), participante (login), admin (login admin)

## Testing
- pytest + pytest-asyncio for async tests
- httpx.AsyncClient with app=app for integration tests
- Factory Boy or Polyfactory for test data
- TestContainers for real DB tests

## Performance
- Async SQLAlchemy (asyncpg) for non-blocking DB
- Redis caching with fastapi-cache2
- Background tasks for non-critical operations
- Connection pooling via SQLAlchemy pool configuration
SKILL_EOF
echo "  python-fastapi/SKILL.md"

# ─── SQLAlchemy skill ─────────────────────────────────────────────────────
mkdir -p .claude/skills/sqlalchemy
cat > .claude/skills/sqlalchemy/SKILL.md << 'SKILL_EOF'
# SQLAlchemy Patterns (ORM VPV)

## Architecture
- SQLAlchemy 2.0+ style with type annotations
- Async by default: AsyncSession + asyncpg (PostgreSQL)
- Declarative models with mapped_column() (not legacy Column())
- Repository pattern: one repository per aggregate root

## Model Definition (Declarative 2.0)
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, func
from datetime import datetime
from uuid import UUID, uuid4

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(150))
    is_admin: Mapped[bool] = mapped_column(default=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    participations: Mapped[list["SeasonParticipant"]] = relationship(back_populates="user", lazy="selectin")
```

## Async Session Setup
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# FastAPI dependency
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

## Query Patterns
```python
from sqlalchemy import select, func, and_, or_

# Single record
stmt = select(User).where(User.id == user_id)
result = await session.execute(stmt)
user = result.scalar_one_or_none()

# List with filtering, ordering, pagination (cursor-based)
stmt = (
    select(User)
    .where(and_(User.is_active == True, User.created_at > cursor_date))
    .order_by(User.created_at.asc())
    .limit(page_size + 1)
)
result = await session.execute(stmt)
users = list(result.scalars().all())

# Eager loading (avoid N+1)
stmt = select(User).options(selectinload(User.posts)).where(User.id == user_id)
```

## Relationships & Loading Strategies
- `lazy="selectin"`: Default for collections — separate SELECT IN query (async-safe)
- `lazy="joined"`: Use for single-valued relationships (many-to-one)
- `lazy="raise"`: Prevent accidental lazy loading — forces explicit loading
- NEVER use `lazy="select"` (default) with async — it will fail
- Use `selectinload()`, `joinedload()` in queries for per-query control

## Migrations (Alembic)
```bash
alembic init alembic
alembic revision --autogenerate -m "add users table"
alembic upgrade head
alembic downgrade -1
alembic history
```

### Alembic Rules
- ALWAYS review autogenerated migrations before applying
- Migrations must be reversible (implement both upgrade and downgrade)
- Separate schema migrations from data migrations
- Never edit migrations that have been applied in production
- Configure async in env.py: `run_async(connectable.run_sync(do_run_migrations))`

## Transactions
```python
# Implicit (via session context manager + commit in dependency)
async with session.begin():
    session.add(user)
    session.add(profile)

# Explicit nested (savepoint)
async with session.begin_nested():
    session.add(risky_operation)
```

## Performance
- Connection pooling: pool_size=20, max_overflow=10 (tune per load)
- pool_pre_ping=True to handle stale connections
- Use `selectinload` for collections, `joinedload` for single relations
- Index frequently filtered/sorted columns in model: `index=True`
- Bulk operations: `session.execute(insert(User).values([...]))` for batch inserts
- Use `returning()` clause to get inserted IDs without extra query

## Rules
- NEVER use synchronous Session with async code
- ALWAYS set `expire_on_commit=False` in async sessions
- ALWAYS use `selectinload` or `joinedload` — never rely on lazy loading in async
- Use `Mapped[type]` annotations on all columns (SQLAlchemy 2.0 style)
- Prefer `scalar_one_or_none()` over `.first()` for single record queries
- Index columns used in WHERE, ORDER BY, and JOIN conditions
SKILL_EOF
echo "  sqlalchemy/SKILL.md"

# ─── VPV Domain skill (negocio especifico) ────────────────────────────────
mkdir -p .claude/skills/vpv-domain
cat > .claude/skills/vpv-domain/SKILL.md << 'SKILL_EOF'
# Liga VPV Fantasy — Domain Rules

## Que es
Liga fantasy de futbol entre amigos basada en La Liga espanola.
Web: ligavpv.com. Reconstruccion completa desde Polymer+MySQL a Next.js+FastAPI+PostgreSQL.

## Modelo de Datos (18 tablas PostgreSQL)

### Tablas principales
| # | Tabla | Proposito |
|---|---|---|
| 1 | `users` | Identidad unica (username, password_hash, display_name, is_admin, telegram_chat_id) |
| 2 | `seasons` | Configuracion por temporada (jornadas, deadline, estado, draft_pool_size) |
| 3 | `scoring_rules` | Reglas de puntuacion configurables por temporada y posicion |
| 4 | `season_payments` | Configuracion economica (cuota, pagos semanales por puesto, premios) |
| 5 | `season_participants` | Vincula usuario <-> temporada (draft_order, is_active) |
| 6 | `teams` | Equipos por temporada (soporta ascensos/descensos) |
| 7 | `players` | Jugadores por temporada (equipo, posicion, foto, owner_id) |
| 8 | `drafts` | Eventos de draft (snake/linear, preseason/winter, estado) |
| 9 | `draft_picks` | Cada eleccion del draft (round, pick_number, jugador, participante) |
| 10 | `matchdays` | Jornadas (numero, estado, counts=TRUE/FALSE, deadline, stats_ok) |
| 11 | `matches` | Partidos (local, visitante, resultado, counts=TRUE/FALSE, stats_ok) |
| 12 | `player_stats` | Stats scraping + puntos calculados por jugador x jornada |
| 13 | `lineups` | Alineacion del participante por jornada (formacion, confirmed, telegram_sent) |
| 14 | `lineup_players` | Los 11 jugadores alineados (posicion, orden, puntos) |
| 15 | `participant_matchday_scores` | Puntuacion total del participante por jornada + ranking |
| 16 | `transactions` | Movimientos economicos (initial_fee, weekly_payment, winter_draft_fee, prize) |
| 17 | `competitions` | Futuro: playoffs, copa (solo estructura, NO implementar) |
| 18 | `valid_formations` | Formaciones permitidas (datos fijos) |

### Relaciones clave
```
users --< season_participants >-- seasons
season_participants --< draft_picks >-- drafts >-- seasons
season_participants --< lineups >-- matchdays >-- seasons
players --< player_stats >-- matchdays
players >-- teams >-- seasons
players.owner_id --> season_participants
lineups --< lineup_players >-- players
matchdays --< matches
```

## Formaciones Validas
| Formacion | DEF | MED | DEL |
|-----------|-----|-----|-----|
| 1-3-4-3 | 3 | 4 | 3 |
| 1-3-5-2 | 3 | 5 | 2 |
| 1-4-4-2 | 4 | 4 | 2 |
| 1-4-3-3 | 4 | 3 | 3 |
| 1-5-4-1 | 5 | 4 | 1 |
| 1-5-3-2 | 5 | 3 | 2 |

Siempre 1 POR + 10 jugadores de campo. Validacion en tabla `valid_formations`.

## Sistema de Puntuacion (configurable por temporada via scoring_rules)

### Participacion
- Jugar: +1 | Titular: +1
- Suplente que entra (evento "Entrada"): NO recibe punto de titular
- Titular sustituido (evento "Salida"): SI recibe punto de titular

### Resultado del equipo
- Victoria: +2 | Empate: +1 | Derrota: 0

### Goles (depende de posicion)
- POR: +10 | DEF: +8 | MED: +7 | DEL: +5

### Imbatibilidad (porteria a cero)
- POR: 0 goles encajados Y >=65 min jugados -> +4 pts. 1 gol -> 0 pts. >1 gol -> penalizacion = -num goles encajados
- DEF: 0 goles encajados Y >=45 min jugados -> +3 pts. Con goles -> 0 pts (sin penalizacion)
- MED/DEL: no aplica

### Acciones positivas
- Gol de penalti: +5 | Asistencia: +2 | Penalti parado (POR): +5
- Tiro al palo: +1 | Penalti forzado: +1

### Acciones negativas
- Penalti fallado: -3 | Gol propia meta: -2 | Amarilla: -1
- Doble amarilla: -3 | Roja directa: -3 | Penalti cometido: -1
- Amarilla quitada por comite: se registra, NO afecta puntuacion

### Valoracion mediatica
- Marca (estrellas): 1=+1, 2=+2, 3=+3, 4=+4, "-"=-1, "SC"=0
- AS (picas): cada pica=+1, "-"=-1, "SC"=0

### Formula total jornada
```
pts_total = pts_play + pts_starter + pts_result + pts_clean_sheet
          + pts_goals + pts_penalty_goals + pts_assists + pts_penalties_saved
          + pts_woodwork + pts_penalties_won
          + pts_penalties_missed + pts_own_goals + pts_yellow + pts_red + pts_pen_committed
          + pts_marca + pts_as
```

## Sistema Economico (configurable por temporada via season_payments)
- initial_fee: Cuota inicial (ej: 50EUR)
- weekly_position: Pago semanal segun puesto (7o: 3EUR, 8o: 5EUR)
- winter_draft_change: 2EUR por cada cambio en draft invierno
- prize: 1o: 200EUR, 2o: 100EUR, 3o: 50EUR
- Transacciones: positivo = debe pagar, negativo = recibe

## Reglas de Negocio Criticas

1. **Partidos que no computan**: dos niveles. `matchdays.counts` para jornada entera, `matches.counts` para partido individual.

2. **Titular vs suplente**: evento "Salida" = era titular. Evento "Entrada" = suplente. Sin evento = titular 90 min.

3. **Imbatibilidad portero**: >1 gol encajado -> penalizacion = num goles (3 goles = -3 pts). Exactamente 1 gol = 0 pts.

4. **Draft serpiente**: Ronda 1 (1->8), Ronda 2 (8->1), Ronda 3 (1->8)... hasta 26 jugadores/participante.

5. **Draft invierno**: lineal (no serpiente). Se paga por cada cambio.

6. **Deadline alineacion**: X minutos antes del primer partido de la jornada (configurable en seasons.lineup_deadline_min).

7. **Scoring rules configurables**: cambiar valores entre temporadas sin tocar codigo. Copiar: INSERT INTO scoring_rules ... SELECT ... FROM scoring_rules WHERE season_id = :old.

8. **stats_ok**: un partido se marca como stats_ok = TRUE cuando tiene <12 valores "SC" en valoraciones mediaticas.

9. **Cambio de posicion**: `players.position` = posicion actual. `player_stats.position` = posicion en esa jornada (fuente de verdad para calculo de puntos).

10. **Cambio de equipo**: `players.team_id` = equipo actual. El equipo real en cada jornada se infiere desde `player_stats.match_id` -> `matches`.

## Roles y Acceso
- **Publico**: clasificacion, jornadas, plantillas, historial drafts, balance global
- **Participante**: alinear jornada (11 + confirmar con password -> imagen -> Telegram), mi balance
- **Admin**: gestion temporada, participantes, scraping, drafts, jornadas, pagos

## Arquitectura de Despliegue
```
[Nginx :443]
  ├── /            -> Next.js (PM2, puerto 3000)
  ├── /api/*       -> FastAPI (uvicorn, puerto 8000)
  └── /static/*    -> Archivos estaticos (fotos jugadores WebP 200x200)

[PostgreSQL :5432]  <- conexion local
[Cron]              -> scraping por jornada
[Telegram Bot]      -> envio alineaciones (python-telegram-bot)
```

## Estrategia de Migracion
```
FASE 1: [Next.js frontend] -> [FastAPI API] -> [MySQL existente]
FASE 2: [Next.js frontend] -> [FastAPI API] -> [PostgreSQL nuevo]
         (frontend no se toca, solo cambia connection string en FastAPI)
```

## Archivos de Referencia
- `claude_data/normas_puntuacion_vpv.md` — Reglas de puntuacion detalladas
- `claude_data/modelo_datos_vpv.md` — Modelo PostgreSQL completo con SQL y consultas ejemplo
- `claude_data/dump-ligavpv-202602201209.sql` — Esquema MySQL actual (6 tablas) para migracion
- `claude_data/CLAUDE.md` — Contexto completo del proyecto
SKILL_EOF
echo "  vpv-domain/SKILL.md"

SKILLS_COUNT=$(find .claude/skills -name "SKILL.md" 2>/dev/null | wc -l)

# ============================================================================
# STEP 2: Create CLAUDE.md
# ============================================================================
echo -e "\n${GREEN}[2/4]${NC} Creating CLAUDE.md..."

cat > CLAUDE.md << 'CLAUDEEOF'
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
CLAUDEEOF
echo "  CLAUDE.md"

# ============================================================================
# STEP 3: Create AGENTS.md (GGA rules)
# ============================================================================
echo -e "\n${GREEN}[3/4]${NC} Creating AGENTS.md..."

cat > AGENTS.md << 'AGENTSEOF'
# Coding Standards — Liga VPV Fantasy

## General
- TypeScript strict mode in frontend (tsconfig.json strict: true)
- Python type hints mandatory in backend (mypy strict or pyright)
- No "any" (TS), no "object" without narrowing, no bare "dict" (Python)
- All exported functions must have explicit return types
- Maximum function length: 30 lines
- Maximum file length: 300 lines
- No console.log (TS) or print() (Python) in production code — use structured logger
- No commented-out code in commits

## Architecture
- Scope Rule: global/shared for 2+ features, features/[name] for 1
- No circular dependencies between modules
- Frontend (Next.js): path aliases @/features/, @/shared/, @/lib/
- Backend (FastAPI): relative within feature, absolute cross-feature
- Business logic must be framework-agnostic (ports & adapters)
- Frontend is pure consumer of API REST — no business logic in Next.js
- All business logic lives in FastAPI services

## Security
- Never hardcode secrets, tokens, or credentials
- Always validate input on server side (Pydantic for FastAPI, Zod for Next.js)
- Use parameterized queries via SQLAlchemy — never string interpolation for SQL
- No eval(), new Function(), or innerHTML with user data
- No sensitive data in logs, error messages, or API responses
- Password hashing: bcrypt or argon2, never plain text

## Testing
- Every new function must have a corresponding test
- Test files co-located with source
- Tests must cover: happy path + error cases + edge cases
- Minimum coverage: 80% on business logic
- Backend: pytest + httpx + TestContainers
- Frontend: Vitest + React Testing Library + Playwright

## Error Handling
- Never use empty catch/except blocks
- All errors must have: code, human message, technical context
- Distinguish user errors (4xx) from system errors (5xx)
- Timeout on all external calls (HTTP, DB, scraping)

## VPV Domain Rules
- NEVER hardcode scoring values — always read from scoring_rules table
- ALWAYS use player_stats.position for scoring calculations
- ALWAYS check both matchdays.counts AND matches.counts for standings
- Formaciones validated against valid_formations table

## Git
- Conventional commits: type(scope): description
- Never mention AI, Claude, LLM, or Copilot in commit messages
- Atomic commits: one logical change per commit
- PR description: what, why, how to test
AGENTSEOF
echo "  AGENTS.md"

# ============================================================================
# STEP 4: Configure GGA
# ============================================================================
echo -e "\n${GREEN}[4/4]${NC} Configuring GGA..."

cat > .gga << 'GGA_EOF'
PROVIDER=claude
RULES_FILE=AGENTS.md
FILE_PATTERNS=*.ts,*.tsx,*.py
EXCLUDE_PATTERNS=*.test.*,*.spec.*,*.d.ts,node_modules/*,dist/*,build/*,.next/*,coverage/*,__pycache__/*,*.pyc,migrations/*,alembic/versions/*
TIMEOUT=60
STRICT_MODE=false
GGA_EOF
echo "  .gga"

if command -v gga &> /dev/null; then
  gga install 2>/dev/null && echo "  Pre-commit hook installed" || echo -e "  ${YELLOW}Could not install hook (is this a git repo?)${NC}"
else
  echo -e "  ${YELLOW}GGA not installed — run 'gga install' once available${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Project ${PROJECT_NAME} initialized with Agent System v3${NC}"
echo ""
echo "  Files created:"
echo "    CLAUDE.md              — Claude Code project config (VPV-specific)"
echo "    AGENTS.md              — GGA quality gate rules (VPV-specific)"
echo "    .gga                   — GGA configuration"
echo "    .claude/skills/        — ${SKILLS_COUNT} architecture-specific skills"
echo ""
echo "  Skills generated:"
find .claude/skills -name "SKILL.md" 2>/dev/null | sort | while read f; do
  skill_name=$(echo "$f" | sed 's|.claude/skills/||;s|/SKILL.md||')
  echo "    ${skill_name}"
done
echo ""
echo "  Stack:"
echo "    Frontend:  Next.js + Tailwind CSS (TypeScript)"
echo "    Backend:   Python + FastAPI + SQLAlchemy"
echo "    Database:  PostgreSQL"
echo "    Auth:      NextAuth.js + JWT"
echo "    ORM:       SQLAlchemy 2.0+ async"
echo "    Hosting:   AlmaLinux 10 (Nginx + PM2 + uvicorn)"
echo ""
echo -e "  ${BOLD}Usage:${NC}"
echo "    Open Claude Code in this project and type:"
echo "    > Use the sdd-orchestrator to plan [your feature]"
echo ""
echo -e "  ${DIM}Customize skills in .claude/skills/ for project-specific patterns.${NC}"
echo -e "  ${DIM}Edit CLAUDE.md to adjust project rules as they evolve.${NC}"
echo -e "  ${DIM}Reference data files in claude_data/ for domain context.${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
