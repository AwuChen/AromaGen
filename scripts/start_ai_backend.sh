#!/usr/bin/env bash

echo "========================================"
echo "  AromaGen AI Backend"
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
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r aromagen/agents/requirements.txt

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY not set!"
fi

echo ""
echo "✅ Starting AI Backend on port 8000..."
echo "   API: http://localhost:8000"
echo ""

uvicorn aromagen.agents.app:app --reload --port 8000
