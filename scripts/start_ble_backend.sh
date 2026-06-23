#!/usr/bin/env bash

echo "========================================"
echo "  AromaGen BLE Backend"
echo "========================================"
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [ ! -d "venv" ]; then
    echo "⚠️  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "✅ Starting BLE Backend on port 5001..."
if [ -n "$SYNC_SERVER_URL" ]; then
    echo "   Sync server: $SYNC_SERVER_URL"
else
    echo "   Sync server: (standalone)"
fi
echo "   Searching for BLE devices with 'wear' in name..."
echo ""

python3 backend.py
