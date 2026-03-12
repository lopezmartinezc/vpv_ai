#!/usr/bin/env bash
# remigrate.sh — Drop, recreate and fully populate the PostgreSQL database.
#
# Usage:
#   ./remigrate.sh              # run everything
#   ./remigrate.sh --dry-run    # migration in dry-run mode (rollback)
#   ./remigrate.sh --skip-post  # skip post-migration scripts
#
# Prerequisites:
#   - migration/.env configured (MySQL + PG credentials)
#   - migration/.venv with dependencies installed
#   - backend/.venv with dependencies installed
#   - PostgreSQL running, user with CREATEDB or superuser for DROP/CREATE
#
# Environment:
#   ADMIN_USER  — username to mark as admin (default: none, manual)
#   PG_SUPERUSER — postgres superuser for drop/create (default: postgres)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MIGRATION_DIR="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_DIR/backend"

# Parse args
DRY_RUN=""
SKIP_POST=false
for arg in "$@"; do
    case $arg in
        --dry-run)   DRY_RUN="--dry-run" ;;
        --skip-post) SKIP_POST=true ;;
    esac
done

# Load PG config from .env
if [ -f "$MIGRATION_DIR/.env" ]; then
    set -a
    source "$MIGRATION_DIR/.env"
    set +a
fi

PG_DB="${PG_DATABASE:-ligavpv}"
PG_SUPER="${PG_SUPERUSER:-postgres}"
PG_OWNER="${PG_USER:-vpv}"
ADMIN_USER="${ADMIN_USER:-carloslopez}"
WEBAPP_USER="${WEBAPP_USER:-vpv}"

echo "============================================================"
echo "  VPV Migration — Full Reset"
echo "============================================================"
echo "  Database:  $PG_DB"
echo "  Owner:     $PG_OWNER"
echo "  Dry-run:   ${DRY_RUN:-no}"
echo "  Skip post: $SKIP_POST"
echo "============================================================"
echo ""

# ---------------------------------------------------------------
# 1. Stop backend (if systemd service exists)
# ---------------------------------------------------------------
if systemctl is-active --quiet vpv-backend 2>/dev/null; then
    echo ">>> Stopping vpv-backend service..."
    sudo systemctl stop vpv-backend
fi

# ---------------------------------------------------------------
# 2. Drop and recreate database
# ---------------------------------------------------------------
if [ -z "$DRY_RUN" ]; then
    echo ">>> Dropping database $PG_DB..."
    sudo -u "$PG_SUPER" psql -c "DROP DATABASE IF EXISTS $PG_DB;" 2>/dev/null || \
        psql -U "$PG_SUPER" -c "DROP DATABASE IF EXISTS $PG_DB;"

    echo ">>> Creating database $PG_DB (owner: $PG_OWNER)..."
    sudo -u "$PG_SUPER" psql -c "CREATE DATABASE $PG_DB OWNER $PG_OWNER;" 2>/dev/null || \
        psql -U "$PG_SUPER" -c "CREATE DATABASE $PG_DB OWNER $PG_OWNER;"
else
    echo ">>> [dry-run] Skipping database drop/create"
fi

# ---------------------------------------------------------------
# 3. Run migration (14 steps: 0-13)
# ---------------------------------------------------------------
echo ""
echo ">>> Running migration..."
cd "$MIGRATION_DIR/scripts"
source "$MIGRATION_DIR/.venv/bin/activate"
python migrate.py $DRY_RUN
deactivate

# Stop here if dry-run or skip-post
if [ -n "$DRY_RUN" ] || [ "$SKIP_POST" = true ]; then
    echo ""
    echo ">>> Migration done. Post-migration steps skipped."
    exit 0
fi

# ---------------------------------------------------------------
# 4. Mark admin user
# ---------------------------------------------------------------
if [ -n "$ADMIN_USER" ]; then
    echo ""
    echo ">>> Marking $ADMIN_USER as admin..."
    PG_CONN="host=${PG_HOST:-localhost} port=${PG_PORT:-5432} user=$PG_OWNER password=${PG_PASSWORD:-} dbname=$PG_DB"
    psql "$PG_CONN" -c "UPDATE users SET is_admin = TRUE WHERE username = '$ADMIN_USER';"
fi

# ---------------------------------------------------------------
# 5. Post-migration data scripts (backend venv)
# ---------------------------------------------------------------
echo ""
echo ">>> Running post-migration scripts..."
cd "$BACKEND_DIR"
source "$BACKEND_DIR/.venv/bin/activate"

echo "  - populate_ownership_log"
python -m scripts.populate_ownership_log

echo "  - fix_winter_draft_drops"
python -m scripts.fix_winter_draft_drops --apply

echo "  - generate_draft_economy_seed (if exists)"
if python -c "import scripts.generate_draft_economy_seed" 2>/dev/null; then
    python -m scripts.generate_draft_economy_seed --apply
fi

echo "  - backfill_weekly_payments"
python -m scripts.backfill_weekly_payments --apply 2>/dev/null || true

# ---------------------------------------------------------------
# 6. Scraping: calendar + photos
# ---------------------------------------------------------------
echo ""
echo ">>> Updating calendar for season 8..."
python -m src.features.scraping.cli update-calendar 8

echo ">>> Downloading player photos for season 8..."
python -m src.features.scraping.cli download-photos 8

deactivate

# ---------------------------------------------------------------
# 7. Restart backend
# ---------------------------------------------------------------
if systemctl list-unit-files vpv-backend.service &>/dev/null; then
    echo ""
    echo ">>> Starting vpv-backend service..."
    sudo systemctl start vpv-backend
fi

echo ""
echo "============================================================"
echo "  Migration complete!"
echo "============================================================"
echo ""
echo "Verify:"
echo "  - https://ligavpv.com/clasificacion"
echo "  - https://ligavpv.com/admin/jornadas"
echo "  - https://ligavpv.com/admin/scraping"
