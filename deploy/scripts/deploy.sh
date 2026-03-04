#!/usr/bin/env bash
# Liga VPV — Deploy script
# Usage: ./deploy/scripts/deploy.sh
# Run from the project root on the production server.
set -euo pipefail

APP_DIR="/opt/vpv"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== VPV Deploy ==="
echo "Repo: $REPO_DIR"
echo "App:  $APP_DIR"

# 1. Pull latest code
echo "--- Pulling latest code ---"
cd "$REPO_DIR"
git pull --ff-only

# 2. Backend
echo "--- Backend: install dependencies ---"
cd "$APP_DIR/backend"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet .

echo "--- Backend: run migrations ---"
.venv/bin/alembic upgrade head

echo "--- Backend: restart ---"
sudo systemctl restart vpv-backend
sleep 2
if systemctl is-active --quiet vpv-backend; then
    echo "Backend: OK"
else
    echo "ERROR: backend failed to start"
    sudo journalctl -u vpv-backend --no-pager -n 20
    exit 1
fi

# 3. Frontend
echo "--- Frontend: install and build ---"
cd "$REPO_DIR/frontend"
npm ci --production=false
npm run build

echo "--- Frontend: copy standalone output ---"
rm -rf "$APP_DIR/frontend"
cp -r .next/standalone "$APP_DIR/frontend"
cp -r .next/static "$APP_DIR/frontend/.next/static"
cp -r public "$APP_DIR/frontend/public" 2>/dev/null || true

echo "--- Frontend: restart PM2 ---"
pm2 restart vpv-frontend || pm2 start "$REPO_DIR/deploy/pm2/ecosystem.config.js"
sleep 2
pm2 status vpv-frontend

# 4. Verify
echo "--- Health check ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo "Health check: OK ($HTTP_CODE)"
else
    echo "WARNING: health check returned $HTTP_CODE"
fi

echo "=== Deploy complete ==="
