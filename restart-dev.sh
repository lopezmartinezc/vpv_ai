#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Stopping existing processes ==="
pkill -f "next dev" 2>/dev/null || true
pkill -f "uvicorn src.app:app" 2>/dev/null || true
sleep 2
rm -f "$PROJECT_DIR/frontend/.next/dev/lock"

echo "=== Starting backend (port 8000) ==="
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
uvicorn src.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "=== Starting frontend (port 3000) ==="
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend PID: $BACKEND_PID (http://localhost:8000)"
echo "Frontend PID: $FRONTEND_PID (http://localhost:3000)"
echo ""
echo "Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
