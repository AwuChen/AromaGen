"""
Scent Sync Server
=================
A WebSocket relay server that keeps two (or more) remote BLE backends
in lock-step.  When one backend sends a "play_sequence" event the server
immediately forwards it to every other connected backend so all devices
smell the same thing at the same time.

Usage
-----
    python sync_server.py

Environment variables
---------------------
    SYNC_HOST   Bind address (default: 0.0.0.0)
    SYNC_PORT   Port number  (default: 8765)

Network topology
----------------
    Computer A ─────────┐
    (BLE backend A)     │  WebSocket
                        ├──► sync_server ◄──┐
    Computer B ─────────┘                   │
    (BLE backend B) ────────────────────────┘

Both BLE backends set  SYNC_SERVER_URL=ws://<host>:<port>  so they
connect here on startup.  After that, pressing "play" on either
machine sends the sequence to the other automatically.
"""

import asyncio
import json
import logging
import os

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [sync] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sync")

# Track all live connections
connected_clients: set = set()


async def handler(websocket):
    client_id = id(websocket)
    addr = websocket.remote_address
    connected_clients.add(websocket)
    log.info("Client connected: %s  (id=%s, total=%d)", addr, client_id, len(connected_clients))

    try:
        async for raw in websocket:
            # Parse incoming message
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Received non-JSON message from %s – ignored", addr)
                continue

            msg_type = data.get("type", "unknown")
            seq_len = len(data.get("sequence", []))
            log.info(
                "Received '%s' from %s  (sequence_len=%d, total_clients=%d)",
                msg_type, addr, seq_len, len(connected_clients),
            )

            # Relay to every OTHER connected client
            others = {c for c in connected_clients if c is not websocket}
            if others:
                log.info("Relaying to %d other client(s)…", len(others))
                results = await asyncio.gather(
                    *[c.send(raw) for c in others],
                    return_exceptions=True,
                )
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        log.warning("Failed to relay to a client: %s", result)
            else:
                log.info("No other clients connected – nothing to relay.")

            # Optionally echo a confirmation back to sender
            ack = json.dumps({"type": "ack", "relayed_to": len(others)})
            try:
                await websocket.send(ack)
            except Exception:
                pass

    except websockets.exceptions.ConnectionClosed as exc:
        log.info("Client %s disconnected: %s", addr, exc)
    except Exception as exc:
        log.error("Unexpected error for %s: %s", addr, exc)
    finally:
        connected_clients.discard(websocket)
        log.info("Client removed: %s  (remaining=%d)", addr, len(connected_clients))


async def main():
    host = os.environ.get("SYNC_HOST", "0.0.0.0")
    port = int(os.environ.get("SYNC_PORT", "8765"))

    print("=" * 55)
    print("  🔄  Scent Sync Server")
    print("=" * 55)
    print(f"  Listening on  {host}:{port}")
    print()
    print("  Setup:")
    print(f"    • On the machine running this server, note its LAN IP")
    print(f"      (e.g. 192.168.x.x or use a tunnel like ngrok/tailscale)")
    print()
    print(f"    • On each BLE-backend machine set the env var:")
    print(f"        export SYNC_SERVER_URL=ws://<this-host>:{port}")
    print(f"      then run: ./start_ble_backend.sh")
    print()
    print("  When both backends are connected any 'Play' action on one")
    print("  machine will automatically trigger the other device too.")
    print("=" * 55)

    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
