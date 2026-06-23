#!/usr/bin/env bash

echo "========================================"
echo "  Restarting AromaGen AI Backend"
echo "========================================"
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    echo "✅ Loaded environment from .env"
fi

PID=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "🔪 Killing process on port 8000: $PID"
    kill -9 $PID 2>/dev/null || true
    sleep 1
fi

exec "$ROOT/scripts/start_ai_backend.sh"
