#!/usr/bin/env bash

# Start all AromaGen services (macOS: opens 3 Terminal tabs)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

echo "╔════════════════════════════════════════════════════════╗"
echo "║  Starting AromaGen Services                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    echo "✅ Loaded environment from .env"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY not set!"
    echo "Copy .env.example to .env and add your key."
    echo ""
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

echo "🚀 Launching services in separate Terminal tabs..."
echo ""

osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$ROOT' && echo '🔵 BLE Backend (Port 5001)' && ./start_ble_backend.sh"
    delay 1
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$ROOT' && echo '🟢 AI Backend (Port 8000)' && ./restart_ai_backend.sh" in front window
    delay 1
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$ROOT' && echo '🟡 Frontend (Port 8080)' && ./start_frontend.sh" in front window
end tell
EOF

echo ""
echo "  🔵 BLE Backend:  http://localhost:5001"
echo "  🟢 AI Backend:   http://localhost:8000"
echo "  🟡 Frontend:     http://localhost:8080"
echo ""
echo "🌐 Open http://localhost:8080"
echo "💡 Stop all: ./kill_all.sh"
