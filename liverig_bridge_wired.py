#!/usr/bin/env python3
"""
LiveRig MIDI Bridge — Wired USB Edition  (v3 — bidirectional + OSC/UDP)
Runs on your Mac. iPad connects via USB cable only.
Requirements: pip install python-rtmidi websockets
"""

import asyncio, json, sys, socket, subprocess, threading, time

WS_PORT  = 8765
UDP_PORT = 9000          # M4L sends JSON state to this port
MIDI_PORT_NAME = "LiveRig Bridge"

try:
    import rtmidi
except ImportError:
    print("ERROR: pip install python-rtmidi"); sys.exit(1)

try:
    import websockets
    try:
        from websockets.asyncio.server import serve as ws_serve
    except ImportError:
        from websockets.legacy.server import serve as ws_serve
except ImportError:
    print("ERROR: pip install websockets"); sys.exit(1)

# ── Virtual MIDI ports ────────────────────────────────────────────────────────
midi_out = rtmidi.MidiOut()
midi_out.open_virtual_port(MIDI_PORT_NAME)

midi_in = rtmidi.MidiIn()
midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
midi_in.open_virtual_port(MIDI_PORT_NAME)

# ── Shared state ──────────────────────────────────────────────────────────────
clients      = set()
clients_lock = asyncio.Lock()
main_loop    = None
rx_count     = 0
tx_count     = 0

# Last known Live state — merged and forwarded to iPad
live_state = {
    "type":         "live_state",
    "bpm":          120.0,
    "transport":    "stopped",
    "bar":          0,
    "beat":         0,
    "timesig":      [4, 4],
    "tracks":       ["Track 1","Track 2","Track 3","Track 4",
                     "Track 5","Track 6","Track 7","Track 8"],
    "clips":        [[0]*8 for _ in range(8)],
    "song":         "",
    "song_len_bars":0,
    "locators":     [],
    "current_locator": ""
}

# ── MIDI IN callback (Ableton → iPad) ────────────────────────────────────────
def midi_in_callback(message, data=None):
    global rx_count
    midi_bytes, _ = message
    if not midi_bytes:
        return
    rx_count += 1
    payload = json.dumps({"type": "midi", "data": list(midi_bytes)})
    async def _broadcast():
        async with clients_lock:
            dead = set()
            for ws in clients:
                try:    await ws.send(payload)
                except: dead.add(ws)
            clients.difference_update(dead)
    if main_loop and not main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(), main_loop)

midi_in.set_callback(midi_in_callback)

# ── Broadcast helpers ─────────────────────────────────────────────────────────
async def broadcast(payload_str):
    async with clients_lock:
        dead = set()
        for ws in clients:
            try:    await ws.send(payload_str)
            except: dead.add(ws)
        clients.difference_update(dead)

async def broadcast_live_state():
    await broadcast(json.dumps(live_state))

# ── UDP server — receives JSON from M4L ──────────────────────────────────────
class UDPProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode())
        except Exception:
            return
        # Merge incoming fields into live_state
        changed = False
        for k, v in msg.items():
            if k in live_state and live_state[k] != v:
                live_state[k] = v
                changed = True
            elif k not in live_state:
                live_state[k] = v
                changed = True
        live_state["type"] = "live_state"
        if changed and main_loop and not main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(broadcast_live_state(), main_loop)

# ── WebSocket server — handles iPad messages ──────────────────────────────────
async def handle_client(websocket, path=None):
    global tx_count
    try:    ip = websocket.remote_address[0]
    except: ip = "unknown"
    print(f"[LiveRig] iPad connected from {ip}", flush=True)
    async with clients_lock:
        clients.add(websocket)
    # Send current state immediately on connect
    await websocket.send(json.dumps(live_state))
    try:
        async for message in websocket:
            try:
                data = json.loads(message) if isinstance(message, str) else {}
                msg_type = data.get("type", "midi") if isinstance(data, dict) else "midi"

                if msg_type == "midi":
                    # Raw MIDI bytes → Ableton
                    raw = data.get("data", data) if isinstance(data, dict) else data
                    if isinstance(raw, list) and raw:
                        midi_out.send_message([int(b) & 0xFF for b in raw])
                        tx_count += 1

                elif msg_type == "setlist_reorder":
                    # iPad reordered the setlist
                    # {type: setlist_reorder, songs: [...]}
                    # Just broadcast back to any other connected clients
                    await broadcast(json.dumps(data))

                elif msg_type == "locator_jump":
                    # iPad wants to jump to a locator
                    # {type: locator_jump, index: N}
                    # Send as SysEx to M4L: F0 7D 30 index F7
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x30, idx, 0xF7])

                elif msg_type == "locator_next":
                    # Jump to next locator
                    midi_out.send_message([0xF0, 0x7D, 0x31, 0x00, 0xF7])

                elif msg_type == "locator_prev":
                    # Jump to previous locator
                    midi_out.send_message([0xF0, 0x7D, 0x32, 0x00, 0xF7])

                elif msg_type == "song_activate":
                    # iPad tapped a song — send PC
                    # {type: song_activate, pc: N}
                    pc = int(data.get("pc", 0)) & 0x7F
                    for ch in range(4):
                        midi_out.send_message([0xC0 | ch, pc])

            except Exception as e:
                print(f"[LiveRig] Bad message: {e}", flush=True)
    except Exception:
        pass
    finally:
        async with clients_lock:
            clients.discard(websocket)
        print(f"[LiveRig] iPad disconnected ({ip})", flush=True)

# ── IP detection ──────────────────────────────────────────────────────────────
def get_all_ips():
    ips = {}
    try:
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        current_if = None
        for line in result.stdout.split('\n'):
            if line and not line.startswith('\t') and not line.startswith(' '):
                current_if = line.split(':')[0]
            if 'inet ' in line and current_if:
                ip = line.strip().split()[1]
                ips[current_if] = ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips['WiFi/eth'] = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return ips

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    ips = get_all_ips()
    print(f"\n{'='*58}")
    print(f"  LiveRig MIDI Bridge — Wired USB Mode  (v3 OSC+MIDI)")
    print(f"{'='*58}")
    print(f"\n  Virtual MIDI ports: '{MIDI_PORT_NAME}'")
    print(f"\n  Ableton Preferences > MIDI:")
    print(f"    Input  '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"    Output '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"\n  M4L device sends UDP JSON → localhost:{UDP_PORT}")
    print(f"\n  Network interfaces:")
    usb_ip = None
    for iface, ip in ips.items():
        label = ""
        if ip.startswith("169.254"):
            label = "  <-- USB (use this on iPad)"
            if usb_ip is None:
                usb_ip = ip
        elif any(k in iface.lower() for k in ("iphone","ipad","usb")):
            label = "  <-- USB interface"
            if usb_ip is None:
                usb_ip = ip
        print(f"    {iface:22s} {ip}{label}")
    if usb_ip:
        print(f"\n  iPad URL: http://{usb_ip}:8080/liverig_controller_served.html")
    print(f"\n  WebSocket : 0.0.0.0:{WS_PORT}")
    print(f"  UDP (M4L) : 0.0.0.0:{UDP_PORT}")
    print(f"{'='*58}\n")

    # Start UDP listener
    await main_loop.create_datagram_endpoint(
        UDPProtocol,
        local_addr=("0.0.0.0", UDP_PORT)
    )
    print(f"[LiveRig] UDP listener ready on port {UDP_PORT}", flush=True)

    # Start WebSocket server
    async with ws_serve(handle_client, "0.0.0.0", WS_PORT):
        print(f"[LiveRig] WebSocket ready on port {WS_PORT}", flush=True)
        await asyncio.Future()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n[LiveRig] Stopped.")
finally:
    midi_in.close_port()
    midi_out.close_port()
