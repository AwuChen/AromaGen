#!/usr/bin/env bash

echo "╔════════════════════════════════════════╗"
echo "║  Terminating AromaGen Processes        ║"
echo "╚════════════════════════════════════════╝"
echo ""

kill_port() {
    PORT=$1
    NAME=$2
    PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "🔪 Killing $NAME (port $PORT)..."
        kill -9 $PIDS 2>/dev/null || true
    else
        echo "✓  $NAME (port $PORT) - not running"
    fi
}

kill_port 5001 "BLE Backend"
kill_port 8000 "AI Backend"
kill_port 8080 "Frontend"
kill_port 8765 "Sync Server"

echo ""
echo "Done. Restart with ./start_all.sh"
