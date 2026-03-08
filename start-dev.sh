#!/usr/bin/env bash
# Liga VPV — Dev environment startup script
#
# Usage: ./start-dev.sh                 (Docker mode, default)
#        ./start-dev.sh --native        (native: PG in Docker, backend+frontend local)
#        ./start-dev.sh --build         (rebuild Docker images)
#        ./start-dev.sh --reset         (wipe DB volume, fresh start)
#        ./start-dev.sh --native --reset
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $PROJECT_DIR/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[vpv]${NC} $*"; }
ok()   { echo -e "${GREEN}[vpv]${NC} $*"; }
warn() { echo -e "${YELLOW}[vpv]${NC} $*"; }
err()  { echo -e "${RED}[vpv]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
BUILD=false
RESET=false
NATIVE=false
for arg in "$@"; do
    case "$arg" in
        --build)  BUILD=true ;;
        --reset)  RESET=true ;;
        --native) NATIVE=true ;;
        --help|-h)
            echo "Usage: $0 [--native] [--build] [--reset]"
            echo ""
            echo "Modes:"
            echo "  (default)   Docker mode — everything runs in containers"
            echo "  --native    Native mode — PG in Docker, backend+frontend run locally"
            echo ""
            echo "Options:"
            echo "  --build     Rebuild Docker images before starting"
            echo "  --reset     Wipe PostgreSQL volume (fresh DB from schema + seed)"
            exit 0
            ;;
        *) err "Unknown option: $arg"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Ensure Docker daemon is running (needed for both modes — PG always in Docker)
# ---------------------------------------------------------------------------
ensure_docker() {
    log "Checking Docker daemon..."
    if ! docker info &>/dev/null; then
        warn "Docker daemon not running — starting it (may ask for sudo password)..."
        if ! sudo systemctl start docker; then
            err "Could not start Docker daemon. Run manually: sudo systemctl start docker"
            exit 1
        fi
        for i in $(seq 1 15); do
            if docker info &>/dev/null; then break; fi
            sleep 1
        done
        if ! docker info &>/dev/null; then
            err "Docker started but not ready. Check: systemctl status docker"
            exit 1
        fi
    fi
    # Ensure current user can access Docker socket
    if ! docker ps &>/dev/null 2>&1; then
        warn "Fixing Docker socket permissions (may ask for sudo password)..."
        sudo chmod 666 /var/run/docker.sock
    fi
    ok "Docker daemon is running"
}

# ---------------------------------------------------------------------------
# Wait for PostgreSQL
# ---------------------------------------------------------------------------
wait_for_pg() {
    log "Waiting for PostgreSQL..."
    local retries=30
    until docker exec vpv-db pg_isready -U vpv -d ligavpv &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            err "PostgreSQL did not become ready in time"
            exit 1
        fi
        sleep 1
    done
    ok "PostgreSQL is ready"
}

# ---------------------------------------------------------------------------
# Check DB has data
# ---------------------------------------------------------------------------
check_db_data() {
    local table_count season_count
    table_count=$(docker exec vpv-db psql -U vpv -d ligavpv -tAc \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo "0")
    season_count=$(docker exec vpv-db psql -U vpv -d ligavpv -tAc \
        "SELECT count(*) FROM seasons" 2>/dev/null || echo "0")

    if [ "$table_count" -lt 10 ] || [ "$season_count" -eq 0 ]; then
        warn "Database appears empty (${table_count} tables, ${season_count} seasons)"
        warn "Run migration: cd migration && source .venv/bin/activate && python scripts/incremental_sync.py"
    else
        ok "Database has ${table_count} tables, ${season_count} seasons"
    fi
}

# ===========================================================================
# DOCKER MODE
# ===========================================================================
start_docker() {
    if $RESET; then
        warn "Resetting database volume..."
        $COMPOSE down -v 2>/dev/null || true
        ok "Database volume wiped"
    fi

    if $BUILD; then
        log "Building Docker images..."
        $COMPOSE build
    fi

    log "Starting all services in Docker..."
    $COMPOSE up -d

    wait_for_pg
    check_db_data

    # Wait for backend
    log "Waiting for backend..."
    local retries=30
    until curl -sf http://localhost:8001/api/seasons &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            warn "Backend not responding yet — check: docker compose logs backend -f"
            break
        fi
        sleep 2
    done
    [ $retries -gt 0 ] && ok "Backend ready at http://localhost:8001/api"

    # Wait for frontend
    log "Waiting for frontend..."
    retries=20
    until curl -sf http://localhost:3000 &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            warn "Frontend not responding yet — check: docker compose logs frontend -f"
            break
        fi
        sleep 3
    done
    [ $retries -gt 0 ] && ok "Frontend ready at http://localhost:3000"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN} Liga VPV Dev (Docker)${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e " Frontend:   ${CYAN}http://localhost:3000${NC}"
    echo -e " Backend:    ${CYAN}http://localhost:8001/api${NC}"
    echo -e " PostgreSQL: ${CYAN}localhost:5433${NC} (vpv/vpv_secret)"
    echo ""
    echo -e " Logs:    docker compose logs -f"
    echo -e " Stop:    docker compose down"
    echo -e " Rebuild: $0 --build"
    echo -e " Fresh:   $0 --reset"
    echo -e "${GREEN}========================================${NC}"
}

# ===========================================================================
# NATIVE MODE — PG in Docker, backend+frontend run locally
# ===========================================================================
start_native() {
    if $RESET; then
        warn "Resetting database volume..."
        $COMPOSE down -v 2>/dev/null || true
        ok "Database volume wiped"
    fi

    # Stop Docker backend/frontend if running, keep only DB
    log "Ensuring only PostgreSQL runs in Docker..."
    $COMPOSE up -d db
    docker stop vpv-backend vpv-frontend 2>/dev/null || true

    wait_for_pg
    check_db_data

    # Kill any existing local processes
    pkill -f "uvicorn src.app:app" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    sleep 1

    # Check backend venv
    if [ ! -f "$PROJECT_DIR/backend/.venv/bin/activate" ]; then
        err "Backend venv not found at backend/.venv"
        err "Create it: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
        exit 1
    fi

    # Check frontend node_modules
    if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
        err "Frontend node_modules not found"
        err "Install: cd frontend && npm install"
        exit 1
    fi

    # Remove Next.js dev lock if stale
    rm -f "$PROJECT_DIR/frontend/.next/dev/lock"

    # Start backend
    log "Starting backend (port 8000)..."
    (
        cd "$PROJECT_DIR/backend"
        source .venv/bin/activate
        export DATABASE_URL="postgresql+asyncpg://vpv:vpv_secret@localhost:5433/ligavpv"
        export DEBUG=true
        export ENVIRONMENT=development
        export CORS_ORIGINS='["http://localhost:3000","http://localhost:3001"]'
        export JWT_SECRET_KEY=dev-secret-key-change-in-production
        uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload 2>&1 | while read -r line; do echo -e "${CYAN}[backend]${NC} $line"; done
    ) &
    BACKEND_PID=$!

    # Start frontend
    log "Starting frontend (port 3000)..."
    (
        cd "$PROJECT_DIR/frontend"
        export NEXT_PUBLIC_API_URL=http://localhost:8000/api
        export NEXTAUTH_URL=http://localhost:3000
        export NEXTAUTH_SECRET=dev-nextauth-secret-change-in-production
        npm run dev 2>&1 | while read -r line; do echo -e "${YELLOW}[frontend]${NC} $line"; done
    ) &
    FRONTEND_PID=$!

    # Wait for backend
    log "Waiting for backend..."
    local retries=30
    until curl -sf http://localhost:8000/api/seasons &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            warn "Backend not responding yet — check output above"
            break
        fi
        sleep 2
    done
    [ $retries -gt 0 ] && ok "Backend ready at http://localhost:8000/api"

    # Wait for frontend
    log "Waiting for frontend..."
    retries=20
    until curl -sf http://localhost:3000 &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            warn "Frontend not responding yet — Next.js takes a moment to compile"
            break
        fi
        sleep 3
    done
    [ $retries -gt 0 ] && ok "Frontend ready at http://localhost:3000"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN} Liga VPV Dev (Native)${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e " Frontend:   ${CYAN}http://localhost:3000${NC}"
    echo -e " Backend:    ${CYAN}http://localhost:8000/api${NC}"
    echo -e " PostgreSQL: ${CYAN}localhost:5433${NC} (vpv/vpv_secret)"
    echo ""
    echo -e " Backend PID:  $BACKEND_PID"
    echo -e " Frontend PID: $FRONTEND_PID"
    echo -e " Press Ctrl+C to stop both"
    echo -e "${GREEN}========================================${NC}"

    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; ok 'Stopped.'; exit 0" INT TERM
    wait
}

# ===========================================================================
# Main
# ===========================================================================
ensure_docker

if $NATIVE; then
    start_native
else
    start_docker
fi
