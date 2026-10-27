#!/usr/bin/env bash

echo "========================================"
echo "  AromaGen Simplex UI"
echo "========================================"
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/aromagen/ui/simplex" || exit 1

echo "✅ Open: http://127.0.0.1:8081"
echo "   (Do not open index.html as a file — fetch needs this server.)"
echo ""
echo "   Requires AI backend :8000 — check http://127.0.0.1:8000/health"
echo "   BLE playback :5001 (from ./start_all.sh)"
echo ""

python3 -m http.server 8081
