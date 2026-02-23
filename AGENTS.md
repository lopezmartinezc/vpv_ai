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
