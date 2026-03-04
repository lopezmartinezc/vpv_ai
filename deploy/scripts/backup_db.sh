#!/usr/bin/env bash
# Liga VPV — PostgreSQL backup
# Cron: 0 3 * * * /opt/vpv/deploy/scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="/opt/vpv/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="$BACKUP_DIR/ligavpv_$TIMESTAMP.dump"

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Starting backup..."
pg_dump -U vpv -d ligavpv -F c -f "$DUMP_FILE"
echo "[$(date -Iseconds)] Backup saved: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Remove backups older than retention period
DELETED=$(find "$BACKUP_DIR" -name "ligavpv_*.dump" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date -Iseconds)] Removed $DELETED old backups (>$RETENTION_DAYS days)"
fi
