#!/bin/bash
# full_sync.sh — Sync lineups from MySQL, recalculate scores, payments, achievements
#
# Usage:
#   ./full_sync.sh                  # sync all pending matchdays
#   ./full_sync.sh 28               # sync only J28
#   ./full_sync.sh 25,26,27,28      # sync multiple matchdays
#   ./full_sync.sh --dry-run        # preview without committing
#   ./full_sync.sh 28 --dry-run     # dry-run for J28

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MIGRATION_VENV="$PROJECT_ROOT/migration/.venv"
BACKEND_VENV="$PROJECT_ROOT/backend/.venv"

# Parse args
MATCHDAYS=""
DRY_RUN=""
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN="--dry-run"
    else
        MATCHDAYS="$arg"
    fi
done

SYNC_ARGS=""
[ -n "$MATCHDAYS" ] && SYNC_ARGS="--matchdays $MATCHDAYS"
[ -n "$DRY_RUN" ] && SYNC_ARGS="$SYNC_ARGS --dry-run"

echo "=============================================="
echo "  Full Sync: MySQL -> PostgreSQL"
echo "  Matchdays: ${MATCHDAYS:-all pending}"
echo "  Dry run:   ${DRY_RUN:-no}"
echo "=============================================="
echo ""

# Step 1: Incremental sync (lineups + scores + rankings)
echo "--- STEP 1: Incremental sync (migration venv) ---"
cd "$SCRIPT_DIR"
source "$MIGRATION_VENV/bin/activate"
python incremental_sync.py $SYNC_ARGS
deactivate

if [ -n "$DRY_RUN" ]; then
    echo ""
    echo "Dry run — skipping payments and achievements."
    exit 0
fi

# Step 2: Delete + regenerate weekly payments for synced matchdays
echo ""
echo "--- STEP 2: Regenerate weekly payments (migration venv) ---"
cd "$SCRIPT_DIR"
source "$MIGRATION_VENV/bin/activate"

# Get season_id and delete existing payments for synced matchdays
python -c "
from config import get_pg_conninfo
import psycopg

conn = psycopg.connect(get_pg_conninfo())
cur = conn.cursor()

cur.execute(\"SELECT id FROM seasons WHERE status = 'active' LIMIT 1\")
row = cur.fetchone()
if not row:
    print('No active season')
    conn.close()
    exit(0)

season_id = row[0]
matchdays = '${MATCHDAYS}'.strip()

if matchdays:
    md_list = [int(m.strip()) for m in matchdays.split(',')]
    # Delete weekly_payment transactions for these matchdays
    cur.execute('''
        DELETE FROM transactions
        WHERE season_id = %s
          AND type = 'weekly_payment'
          AND matchday_id IN (
              SELECT id FROM matchdays WHERE season_id = %s AND number = ANY(%s)
          )
    ''', (season_id, season_id, md_list))
    print(f'Deleted {cur.rowcount} weekly_payment transactions for matchdays {md_list}')
else:
    # Delete ALL weekly payments for the season
    cur.execute('''
        DELETE FROM transactions
        WHERE season_id = %s AND type = 'weekly_payment'
    ''', (season_id,))
    print(f'Deleted {cur.rowcount} weekly_payment transactions')

conn.commit()
conn.close()
"
deactivate

# Now regenerate payments
source "$BACKEND_VENV/bin/activate"
cd "$PROJECT_ROOT/backend"
PYTHONPATH="$PROJECT_ROOT/backend" python -m scripts.backfill_weekly_payments
deactivate

# Step 3: Re-evaluate achievements
echo ""
echo "--- STEP 3: Re-evaluate achievements (backend venv) ---"

# Get season_id
cd "$SCRIPT_DIR"
source "$MIGRATION_VENV/bin/activate"
SEASON_ID=$(python -c "
from config import get_pg_conninfo
import psycopg
conn = psycopg.connect(get_pg_conninfo())
cur = conn.cursor()
cur.execute(\"SELECT id FROM seasons WHERE status = 'active' LIMIT 1\")
row = cur.fetchone()
print(row[0] if row else '')
conn.close()
")
deactivate

if [ -z "$SEASON_ID" ]; then
    echo "No active season found — skipping achievements."
else
    source "$BACKEND_VENV/bin/activate"
    cd "$PROJECT_ROOT/backend"
    PYTHONPATH="$PROJECT_ROOT/backend" python -c "
import asyncio
import sys
sys.path.insert(0, '.')

async def run():
    from src.core.database import AsyncSessionLocal, engine
    from src.features.achievements.service import AchievementService
    async with AsyncSessionLocal() as session:
        svc = AchievementService(session)
        results = await svc.evaluate_all_matchdays($SEASON_ID)
        total = sum(r.granted for r in results)
        print(f'Evaluated {len(results)} matchdays, granted {total} achievements')
    await engine.dispose()

asyncio.run(run())
"
    deactivate
fi

echo ""
echo "=============================================="
echo "  Full sync complete!"
echo "=============================================="
