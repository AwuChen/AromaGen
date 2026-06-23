#!/usr/bin/env bash

echo "========================================"
echo "  AromaGen Frontend"
echo "========================================"
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/aromagen/ui/demo" || exit 1

echo "✅ http://localhost:8080"
echo ""

python3 -m http.server 8080
