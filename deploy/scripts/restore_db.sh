#!/usr/bin/env bash
# Liga VPV — Restore PostgreSQL from backup
# Usage: ./deploy/scripts/restore_db.sh /opt/vpv/backups/ligavpv_YYYYMMDD_HHMMSS.dump
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <dump_file>"
    echo "Available backups:"
    ls -lht /opt/vpv/backups/ligavpv_*.dump 2>/dev/null || echo "  (none found)"
    exit 1
fi

DUMP_FILE="$1"

if [ ! -f "$DUMP_FILE" ]; then
    echo "ERROR: File not found: $DUMP_FILE"
    exit 1
fi

echo "WARNING: This will DROP and recreate all tables in ligavpv!"
echo "Dump file: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"
read -p "Continue? [y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Stopping backend..."
sudo systemctl stop vpv-backend || true

echo "Restoring database..."
pg_restore -U vpv -d ligavpv --clean --if-exists "$DUMP_FILE"

echo "Starting backend..."
sudo systemctl start vpv-backend

echo "Restore complete. Verifying..."
curl -s http://localhost:8000/api/health | python3 -m json.tool
