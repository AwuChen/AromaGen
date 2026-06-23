"""
DeathScent BLE Backend
======================
Flask server that drives a local BLE wearable device and optionally
stays in sync with a remote device via a WebSocket sync server.

Environment variables
---------------------
    BLE_DEVICE_ADDRESS   Pin this backend to a specific BLE device by its
                         hardware address (MAC on Linux, UUID on macOS).
                         Run  python3 scan_devices.py  to discover addresses.
                         If unset, the backend auto-scans for the first device
                         whose name contains BLE_DEVICE_KEYWORD ("wear").

    BLE_DEVICE_KEYWORD   Keyword to match in device name during auto-scan.
                         Default: "wear".  Ignored when BLE_DEVICE_ADDRESS is set.

    SYNC_SERVER_URL      WebSocket URL of the sync_server.py process.
                         e.g.  ws://192.168.1.42:8765
                         Leave unset to run standalone (no sync).

Endpoints
---------
    POST /play_scent      Play a single scent locally (+ broadcast to peers)
    POST /play_sequence   Play a sequence locally (+ broadcast to peers)
    GET  /test_connection Test BLE connectivity
    GET  /health          Liveness probe
    GET  /sync_status     Show WebSocket sync connection state
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
import json
import logging
import os
import queue
import threading
import time

from bleak import BleakClient, BleakScanner

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [backend] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# BLE configuration
# ---------------------------------------------------------------------------
DEVICE_NAME_KEYWORD = os.environ.get("BLE_DEVICE_KEYWORD", "wear")
DEVICE_ADDRESS_OVERRIDE = os.environ.get("BLE_DEVICE_ADDRESS", None)
WRITE_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

_cached_device_address = None

# ---------------------------------------------------------------------------
# Sync configuration
# ---------------------------------------------------------------------------
SYNC_SERVER_URL = os.environ.get("SYNC_SERVER_URL", None)

# Queue used by Flask routes to push messages into the WebSocket send loop.
# Items are raw JSON strings.
_sync_send_queue: queue.Queue = queue.Queue()

# Human-readable connection state shown by /sync_status
_sync_state = {
    "enabled": bool(SYNC_SERVER_URL),
    "url": SYNC_SERVER_URL,
    "connected": False,
    "last_sent": None,
    "last_received": None,
}


# ---------------------------------------------------------------------------
# BLE helpers
# ---------------------------------------------------------------------------

async def find_device_by_name(keyword: str = DEVICE_NAME_KEYWORD, timeout: float = 10.0):
    global _cached_device_address

    # If a specific device address is pinned via env var, use it directly.
    if DEVICE_ADDRESS_OVERRIDE:
        log.info("Using pinned device address: %s", DEVICE_ADDRESS_OVERRIDE)
        return DEVICE_ADDRESS_OVERRIDE

    if _cached_device_address:
        try:
            log.info("Checking cached device: %s", _cached_device_address)
            async with BleakClient(_cached_device_address, timeout=5.0) as client:
                if client.is_connected:
                    log.info("Cached device still available")
                    return _cached_device_address
        except Exception as e:
            log.warning("Cached device no longer available: %s", e)
            _cached_device_address = None

    log.info("Scanning for devices with '%s' in name…", keyword)
    devices = await BleakScanner.discover(timeout=timeout)

    for device in devices:
        if device.name and keyword.lower() in device.name.lower():
            log.info("Found device: %s (%s)", device.name, device.address)
            _cached_device_address = device.address
            return device.address

    log.warning("No device found with '%s' in name", keyword)
    return None


def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def build_scent_command(scent_id: int, duration_sec: int) -> bytes:
    start = bytes([0xF5])
    header = bytes([0x00, 0x00, 0x00, 0x01])
    cmd_type = bytes([0x02])
    subcmd = bytes([0x05])
    channel = bytes([scent_id])
    padding = bytes([0x00, 0x00])
    duration_ms = duration_sec * 1000
    duration_bytes = duration_ms.to_bytes(2, "big")
    body = header + cmd_type + subcmd + channel + padding + duration_bytes
    crc_bytes = crc16_modbus(body)
    end = bytes([0x55])
    return start + body + crc_bytes + end


async def play_scent_ble(scent_id: int, duration: int):
    try:
        device_address = await find_device_by_name()
        if not device_address:
            return {"status": "error", "message": f"Device with '{DEVICE_NAME_KEYWORD}' in name not found."}

        async with BleakClient(device_address) as client:
            await client.connect()
            if not client.is_connected:
                return {"status": "error", "message": "Failed to connect to device"}

            cmd_bytes = build_scent_command(scent_id, duration)
            log.info("Sending scent %d for %ds  cmd=%s", scent_id, duration, cmd_bytes.hex().upper())
            await client.write_gatt_char(WRITE_CHAR_UUID, cmd_bytes)
            log.info("Scent %d sent successfully", scent_id)
            return {"status": "success", "message": f"Scent {scent_id} sent for {duration} seconds"}

    except Exception as e:
        log.error("Error sending scent: %s", e)
        return {"status": "error", "message": str(e)}


async def play_sequence_ble(sequence: list):
    try:
        device_address = await find_device_by_name()
        if not device_address:
            return {"status": "error", "message": f"Device with '{DEVICE_NAME_KEYWORD}' in name not found."}

        async with BleakClient(device_address) as client:
            await client.connect()
            if not client.is_connected:
                return {"status": "error", "message": "Failed to connect to device"}

            log.info("Playing sequence of %d scents", len(sequence))
            for item in sequence:
                scent_id = item.get("scent_id", item.get("id", 1))
                duration = item.get("duration", 5)
                try:
                    cmd_bytes = build_scent_command(scent_id, duration)
                    log.info("Sending scent %d for %ds", scent_id, duration)
                    await client.write_gatt_char(WRITE_CHAR_UUID, cmd_bytes)
                    await asyncio.sleep(duration)
                except Exception as e:
                    log.error("Error sending scent %d: %s", scent_id, e)
                    continue

            return {"status": "success", "message": "Sequence completed"}

    except Exception as e:
        log.error("Connection error: %s", e)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Sync helpers (called from Flask routes)
# ---------------------------------------------------------------------------

def _enqueue_sync(msg_type: str, payload: dict):
    """Thread-safe: put a message on the outbound sync queue."""
    if not SYNC_SERVER_URL:
        return
    message = json.dumps({"type": msg_type, "timestamp": time.time(), **payload})
    _sync_send_queue.put_nowait(message)
    _sync_state["last_sent"] = time.strftime("%H:%M:%S")
    log.info("Enqueued sync message: type=%s", msg_type)


# ---------------------------------------------------------------------------
# WebSocket sync client (runs in its own daemon thread + event loop)
# ---------------------------------------------------------------------------

async def _ws_send_loop(ws):
    """Drain _sync_send_queue and forward messages to the sync server."""
    while True:
        try:
            msg = _sync_send_queue.get_nowait()
            await ws.send(msg)
            log.info("Sync → sent to server")
        except queue.Empty:
            await asyncio.sleep(0.05)  # poll every 50 ms
        except Exception as e:
            log.warning("Sync send error: %s", e)
            break


async def _ws_recv_loop(ws):
    """
    Receive messages from the sync server and play them on the local BLE
    device WITHOUT re-broadcasting (loop prevention).
    """
    try:
        async for raw in ws:
            _sync_state["last_received"] = time.strftime("%H:%M:%S")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Sync ← non-JSON message ignored")
                continue

            msg_type = data.get("type")

            if msg_type == "ack":
                log.info("Sync ← ack (relayed_to=%s)", data.get("relayed_to"))
                continue

            if msg_type == "play_sequence":
                sequence = data.get("sequence", [])
                log.info("Sync ← play_sequence (%d scents) – playing on local device", len(sequence))
                # Spawn a fresh thread so BLE doesn't block the WS connection
                t = threading.Thread(
                    target=lambda seq=sequence: asyncio.run(play_sequence_ble(seq)),
                    daemon=True,
                    name="sync-ble-player",
                )
                t.start()

            elif msg_type == "play_scent":
                scent_id = data.get("scent_id", 1)
                duration = data.get("duration", 5)
                log.info("Sync ← play_scent id=%d dur=%d – playing on local device", scent_id, duration)
                t = threading.Thread(
                    target=lambda sid=scent_id, dur=duration: asyncio.run(play_scent_ble(sid, dur)),
                    daemon=True,
                    name="sync-ble-player",
                )
                t.start()

            else:
                log.info("Sync ← unknown message type '%s' – ignored", msg_type)

    except Exception as e:
        log.warning("Sync receive loop ended: %s", e)


async def _sync_client_loop():
    """Persistent reconnect loop for the sync WebSocket client."""
    import websockets  # imported here so the module still works without it

    while True:
        try:
            log.info("Connecting to sync server: %s", SYNC_SERVER_URL)
            async with websockets.connect(
                SYNC_SERVER_URL,
                ping_interval=20,
                ping_timeout=10,
                open_timeout=10,
            ) as ws:
                _sync_state["connected"] = True
                log.info("Connected to sync server ✅")

                send_task = asyncio.create_task(_ws_send_loop(ws))
                recv_task = asyncio.create_task(_ws_recv_loop(ws))

                # Run until either direction fails (then reconnect)
                done, pending = await asyncio.wait(
                    [send_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()

        except Exception as e:
            log.warning("Sync server unreachable: %s – retrying in 5 s…", e)
        finally:
            _sync_state["connected"] = False

        await asyncio.sleep(5)


def _start_sync_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_sync_client_loop())
    except Exception as e:
        log.error("Sync thread crashed: %s", e)


if SYNC_SERVER_URL:
    _t = threading.Thread(target=_start_sync_thread, daemon=True, name="sync-ws-client")
    _t.start()
    log.info("Sync client thread started → %s", SYNC_SERVER_URL)
else:
    log.info("SYNC_SERVER_URL not set – running in standalone mode (no sync)")


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/play_scent", methods=["POST"])
def play_scent():
    try:
        data = request.get_json()
        scent_id = data.get("scent_id", 1)
        duration = data.get("duration", 5)

        if not isinstance(scent_id, int) or scent_id < 1 or scent_id > 12:
            return jsonify({"status": "error", "message": "Invalid scent_id. Must be between 1-12"}), 400
        if not isinstance(duration, int) or duration < 1 or duration > 60:
            return jsonify({"status": "error", "message": "Invalid duration. Must be between 1-60 seconds"}), 400

        # Play locally
        result = asyncio.run(play_scent_ble(scent_id, duration))

        # Broadcast to remote device(s) via sync server
        _enqueue_sync("play_scent", {"scent_id": scent_id, "duration": duration})

        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/play_sequence", methods=["POST"])
def play_sequence():
    try:
        data = request.get_json()
        sequence = data.get("sequence", [])

        if not sequence:
            return jsonify({"status": "error", "message": "No sequence provided"}), 400

        for i, item in enumerate(sequence):
            if not isinstance(item, dict):
                return jsonify({"status": "error", "message": f"Item {i} must be a dictionary"}), 400
            scent_id = item.get("scent_id", item.get("id", 1))
            duration = item.get("duration", 5)
            if not isinstance(scent_id, int) or scent_id < 1 or scent_id > 12:
                return jsonify({"status": "error", "message": f"Invalid scent_id in item {i}. Must be 1-12"}), 400
            if not isinstance(duration, int) or duration < 1 or duration > 60:
                return jsonify({"status": "error", "message": f"Invalid duration in item {i}. Must be 1-60 s"}), 400

        # Broadcast to remote device(s) BEFORE playing locally so both start
        # at nearly the same time (network latency is usually < 100 ms on LAN).
        _enqueue_sync("play_sequence", {"sequence": sequence})

        # Play locally
        result = asyncio.run(play_sequence_ble(sequence))

        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/test_connection", methods=["GET"])
def test_connection():
    try:
        result = asyncio.run(test_ble_connection())
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/sync_status", methods=["GET"])
def sync_status():
    """Return current state of the WebSocket sync connection."""
    return jsonify({
        "sync_enabled": _sync_state["enabled"],
        "sync_server_url": _sync_state["url"],
        "sync_connected": _sync_state["connected"],
        "last_sent": _sync_state["last_sent"],
        "last_received": _sync_state["last_received"],
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Backend is running"})


@app.route("/")
def index():
    return send_from_directory(".", "frontend.html")


# ---------------------------------------------------------------------------
# BLE test (unchanged from original)
# ---------------------------------------------------------------------------

async def test_ble_connection():
    try:
        log.info("Searching for device with '%s' in name…", DEVICE_NAME_KEYWORD)
        device_address = await find_device_by_name()

        if not device_address:
            return {
                "status": "error",
                "message": (
                    f"Device with '{DEVICE_NAME_KEYWORD}' in name not found.\n\n"
                    "Please check:\n"
                    "1. Device is powered ON\n"
                    "2. Device is in range\n"
                    f"3. Device name contains '{DEVICE_NAME_KEYWORD}'\n"
                    "4. Bluetooth is enabled on your computer"
                ),
                "keyword": DEVICE_NAME_KEYWORD,
            }

        log.info("Testing connection to %s…", device_address)
        async with BleakClient(device_address, timeout=10.0) as client:
            await client.connect()

            if not client.is_connected:
                return {"status": "error", "message": "Failed to connect to device", "address": device_address}

            device_name = "Unknown"
            devices = await BleakScanner.discover(timeout=2.0)
            for dev in devices:
                if dev.address == device_address:
                    device_name = dev.name if dev.name else "Unknown"
                    break

            found_char = False
            try:
                if hasattr(client, "services"):
                    for service in client.services:
                        for char in service.characteristics:
                            if char.uuid.lower() == WRITE_CHAR_UUID.lower():
                                found_char = True
                                break
                        if found_char:
                            break
            except Exception:
                found_char = True  # assume OK if we can't enumerate

            suffix = "Write Characteristic: Available" if found_char else "Could not verify write characteristic"
            return {
                "status": "success",
                "message": f"✅ Device connected!\n\nDevice: {device_name}\nAddress: {device_address}\n{suffix}",
                "address": device_address,
                "device_name": device_name,
            }

    except asyncio.TimeoutError:
        return {
            "status": "error",
            "message": "⏱️ Connection timeout. Device not responding.",
            "keyword": DEVICE_NAME_KEYWORD,
        }
    except Exception as e:
        error_msg = str(e)
        if "was not found" in error_msg.lower():
            return {
                "status": "error",
                "message": (
                    f"❌ Device not found.\n\nPlease check:\n"
                    "1. Device is powered ON\n"
                    "2. Device is in range\n"
                    f"3. Device name contains '{DEVICE_NAME_KEYWORD}'\n"
                    "4. Device is not connected to another app"
                ),
                "keyword": DEVICE_NAME_KEYWORD,
                "details": error_msg,
            }
        return {
            "status": "error",
            "message": f"Connection error: {error_msg}",
            "keyword": DEVICE_NAME_KEYWORD,
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("🌹  DeathScent BLE Backend")
    print("=" * 60)
    if DEVICE_ADDRESS_OVERRIDE:
        print(f"  Device address : {DEVICE_ADDRESS_OVERRIDE}  (pinned)")
    else:
        print(f"  Device keyword : {DEVICE_NAME_KEYWORD}  (auto-scan)")
    print(f"  Characteristic : {WRITE_CHAR_UUID}")
    print(f"  Sync server    : {SYNC_SERVER_URL or '(standalone – no sync)'}")
    print("=" * 60)
    print()
    app.run(debug=False, host="0.0.0.0", port=5001)
