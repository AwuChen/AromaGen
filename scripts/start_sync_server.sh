#!/usr/bin/env bash

echo "========================================"
echo "  AromaGen Sync Server"
echo "========================================"
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

SYNC_HOST="${SYNC_HOST:-0.0.0.0}"
SYNC_PORT="${SYNC_PORT:-8765}"

echo "✅ ws://${SYNC_HOST}:${SYNC_PORT}"
export SYNC_HOST SYNC_PORT
python3 sync_server.py
