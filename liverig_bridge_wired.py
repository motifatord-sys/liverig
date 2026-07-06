#!/usr/bin/env python3
"""
LiveRig MIDI Bridge  (v3 — bidirectional + OSC/UDP)
Runs on your Mac. The iPad connects wirelessly over the local network
(Safari -> this bridge's WebSocket server) -- the "Wired USB Edition" name
and "USB cable only" comment are stale as of 2026-07-02: LiveRig has run
over WiFi for a while now, USB is only ever used for ad-hoc debugging
(e.g. Safari's remote Web Inspector), never required for normal operation.
Requirements: pip install python-rtmidi websockets
"""

import asyncio, json, os, sys, socket, subprocess, threading, time
from urllib.parse import urlparse, parse_qs

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

# ── WebSocket auth token (2026-07-06) ─────────────────────────────────────────
# The WebSocket used to accept ANY client on the LAN with zero auth. LiveRig.app
# generates a token once (see _ensure_token in liverig_app.py), injects it into
# the served controller page, and this bridge requires it as ?token=... on the
# WS URL. If the token file is missing/empty (dev runs outside the app), the
# bridge runs open, exactly as before -- auth is only enforced when the app has
# provisioned a token.
TOKEN_FILE = os.path.expanduser("~/Library/Application Support/LiveRig/ws_token")

def load_auth_token():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""

AUTH_TOKEN = load_auth_token()

def _client_token(websocket, path):
    """Extract ?token=... from the WS request across websockets API versions."""
    raw = path
    if not raw:
        raw = getattr(getattr(websocket, "request", None), "path", None)
    if not raw:
        raw = getattr(websocket, "path", "") or ""
    try:
        qs = parse_qs(urlparse(raw).query)
        return (qs.get("token") or [""])[0]
    except Exception:
        return ""

# ── KBD fader names (portable across iPads) ───────────────────────────────────
# iPad-authored names for KBD faders (e.g. Omnisphere patch names). Persisted
# here on the Mac and pushed to every client on connect, so a name typed on one
# iPad shows on all of them and survives an app restart -- unlike the old
# per-device localStorage. Keys are "<kbd>_<fader>" (matches the controller's
# kbdFaderNameKey). Stored in the app's own Application Support dir (no macOS
# Desktop-permission prompt, not clobbered by the launcher's per-file copies).
FADER_NAMES_FILE = os.path.expanduser(
    "~/Library/Application Support/LiveRig/kbd_fader_names.json")
kbd_fader_names = {}

def load_fader_names():
    global kbd_fader_names
    try:
        with open(FADER_NAMES_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            kbd_fader_names = {str(k): str(v) for k, v in d.items() if v}
            print(f"[LiveRig] loaded {len(kbd_fader_names)} KBD fader name(s)", flush=True)
    except FileNotFoundError:
        kbd_fader_names = {}
    except Exception as e:
        print(f"[LiveRig] fader-names load failed: {e}", flush=True)
        kbd_fader_names = {}

def save_fader_names():
    try:
        os.makedirs(os.path.dirname(FADER_NAMES_FILE), exist_ok=True)
        with open(FADER_NAMES_FILE, "w", encoding="utf-8") as fh:
            json.dump(kbd_fader_names, fh)
    except Exception as e:
        print(f"[LiveRig] fader-names save failed: {e}", flush=True)

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

async def handle_http(reader, writer):
    """Simple HTTP server to receive JSON POSTs from M4L JS object."""
    try:
        head = await reader.read(4096)
        text = head.decode('utf-8', errors='replace')
        # Extract body (after double newline)
        if '\r\n\r\n' in text:
            body = text.split('\r\n\r\n', 1)[1]
        elif '\n\n' in text:
            body = text.split('\n\n', 1)[1]
        else:
            body = ''
        body = body.strip()
        if body:
            try:
                msg = json.loads(body)
                changed = False
                for k, v in msg.items():
                    if live_state.get(k) != v:
                        live_state[k] = v
                        changed = True
                live_state["type"] = "live_state"
                if changed:
                    await broadcast_live_state()
                    print(f"[LiveRig] HTTP state: bpm={live_state.get('bpm')} transport={live_state.get('transport')} bar={live_state.get('bar')}", flush=True)
            except Exception as e:
                print(f"[LiveRig] HTTP parse error: {e}", flush=True)
        # Send 200 OK
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
        await writer.drain()
    except Exception as e:
        pass
    finally:
        writer.close()



# ── UDP server — receives JSON from M4L ──────────────────────────────────────
class UDPProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        # udpsend in Max wraps data as OSC — try multiple decode strategies
        msg = None

        # Strategy 1: plain JSON (if using a custom sender)
        try:
            msg = json.loads(data.decode('utf-8'))
        except Exception:
            pass

        # Strategy 2: OSC string message — skip OSC address header
        # OSC packets start with / and are null-padded
        if msg is None:
            try:
                text = data.decode('utf-8', errors='ignore')
                # Find first { which starts the JSON
                brace = text.find('{')
                if brace != -1:
                    msg = json.loads(text[brace:])
            except Exception:
                pass

        # Strategy 3: scan raw bytes for JSON
        if msg is None:
            try:
                raw = data.decode('latin-1', errors='replace')
                brace = raw.find('{')
                end = raw.rfind('}')
                if brace != -1 and end != -1:
                    msg = json.loads(raw[brace:end+1])
            except Exception:
                pass

        if msg is None:
            print(f"[LiveRig] UDP: could not parse {len(data)} bytes from {addr}", flush=True)
            print(f"[LiveRig] UDP hex: {data[:120].hex()}", flush=True)
            print(f"[LiveRig] UDP str: {data[:120]}", flush=True)
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
    if AUTH_TOKEN and _client_token(websocket, path) != AUTH_TOKEN:
        print(f"[LiveRig] REJECTED unauthenticated client from {ip}", flush=True)
        try:
            await websocket.close(code=4401, reason="auth required")
        except Exception:
            pass
        return
    print(f"[LiveRig] iPad connected from {ip}", flush=True)
    async with clients_lock:
        clients.add(websocket)
    # Send current state immediately on connect
    await websocket.send(json.dumps(live_state))
    # Push the portable KBD fader names so this client matches every other one.
    try:
        await websocket.send(json.dumps({"type": "kbd_fader_names", "names": kbd_fader_names}))
    except Exception as e:
        print(f"[LiveRig] fader-names send failed: {e}", flush=True)
    # Ask the Remote Script to re-emit everything it knows over MIDI SysEx --
    # KBD/stem/aux device names+colors+volumes, binding statuses, cues,
    # scenes, looper states, etc (see SX_REQUEST_FULL_STATE / _emit_full_state
    # in LiveRig.py). Before this fix, that data was only ever pushed ONCE,
    # ~2 seconds after Ableton first loads the Remote Script -- nothing ever
    # re-requested it. So if this bridge (or the whole LiveRig.app) crashed
    # and restarted mid-show, or the iPad's Safari tab reloaded, or a second
    # iPad connected, the client had nothing until Ableton itself was
    # reloaded -- not an option mid-performance. The Remote Script itself
    # never went stale; it kept tracking Ableton correctly the entire time.
    # This was purely a missing "please resend" handshake. 2026-07-03.
    try:
        midi_out.send_message([0xF0, 0x7D, 0x4A, 0x00, 0xF7])
        print(f"[LiveRig] requested full-state resync from Ableton for {ip}", flush=True)
    except Exception as e:
        print(f"[LiveRig] full-state resync request failed: {e}", flush=True)
    try:
        async for message in websocket:
            try:
                data = json.loads(message) if isinstance(message, str) else message

                # Legacy format: raw MIDI byte array [0xB0, cc, val]
                if isinstance(data, list):
                    if data and all(isinstance(b, (int, float)) for b in data):
                        midi_out.send_message([int(b) & 0xFF for b in data])
                        tx_count += 1
                        if tx_count % 50 == 0:
                            print(f"[LiveRig] → {tx_count} MIDI msgs to Ableton", flush=True)
                    continue

                if not isinstance(data, dict):
                    continue

                msg_type = data.get("type", "midi")

                if msg_type == "midi":
                    # New format: {type:"midi", data:[bytes]}
                    raw = data.get("data", [])
                    if isinstance(raw, list) and raw:
                        midi_out.send_message([int(b) & 0xFF for b in raw])
                        tx_count += 1

                elif msg_type == "setlist_reorder":
                    await broadcast(json.dumps(data))

                elif msg_type == "set_kbd_fader_name":
                    # An iPad renamed a KBD fader. Persist it and rebroadcast the
                    # full name set so every connected iPad updates in sync.
                    key = str(data.get("key", "")).strip()
                    name = data.get("name", "")
                    if key:
                        if name is None or str(name).strip() == "":
                            kbd_fader_names.pop(key, None)
                        else:
                            kbd_fader_names[key] = str(name)
                        save_fader_names()
                        await broadcast(json.dumps(
                            {"type": "kbd_fader_names", "names": kbd_fader_names}))

                elif msg_type == "locator_jump":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x30, idx, 0xF7])

                elif msg_type == "locator_next":
                    midi_out.send_message([0xF0, 0x7D, 0x31, 0x00, 0xF7])

                elif msg_type == "locator_prev":
                    midi_out.send_message([0xF0, 0x7D, 0x32, 0x00, 0xF7])

                elif msg_type == "scene_fire":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x33, idx, 0xF7])

                elif msg_type == "transport_play":
                    midi_out.send_message([0xF0, 0x7D, 0x40, 0x00, 0xF7])

                elif msg_type == "transport_stop":
                    midi_out.send_message([0xF0, 0x7D, 0x41, 0x00, 0xF7])

                elif msg_type == "transport_record":
                    midi_out.send_message([0xF0, 0x7D, 0x42, 0x00, 0xF7])

                elif msg_type == "transport_overdub":
                    midi_out.send_message([0xF0, 0x7D, 0x43, 0x00, 0xF7])

                elif msg_type == "transport_metronome":
                    midi_out.send_message([0xF0, 0x7D, 0x44, 0x00, 0xF7])

                elif msg_type == "transport_loop":
                    midi_out.send_message([0xF0, 0x7D, 0x45, 0x00, 0xF7])

                elif msg_type == "transport_punch":
                    midi_out.send_message([0xF0, 0x7D, 0x46, 0x00, 0xF7])

                elif msg_type == "transport_tap":
                    midi_out.send_message([0xF0, 0x7D, 0x47, 0x00, 0xF7])

                elif msg_type == "transport_undo":
                    midi_out.send_message([0xF0, 0x7D, 0x48, 0x00, 0xF7])

                elif msg_type == "transport_redo":
                    midi_out.send_message([0xF0, 0x7D, 0x49, 0x00, 0xF7])

                elif msg_type == "loop_rec":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x4B, idx, 0xF7])

                elif msg_type == "loop_play":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x4C, idx, 0xF7])

                elif msg_type == "loop_stop":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x4D, idx, 0xF7])

                elif msg_type == "loop_undo":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x4E, idx, 0xF7])

                elif msg_type == "loop_quant":
                    idx = int(data.get("index", 0)) & 0x07
                    qval = int(data.get("value", 0)) & 0x0F
                    packed = ((idx << 4) | qval) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x4F, packed, 0xF7])

                elif msg_type == "blue_hand_on":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x50, idx, 0xF7])

                elif msg_type == "blue_hand_off":
                    idx = int(data.get("index", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x51, idx, 0xF7])

                elif msg_type == "clip_fire":
                    scene = int(data.get("scene", 0)) & 0x0F
                    track = int(data.get("track", 0)) & 0x07
                    packed = ((scene << 3) | track) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x52, packed, 0xF7])

                elif msg_type == "clip_stop_track":
                    track = int(data.get("track", 0)) & 0x7F
                    midi_out.send_message([0xF0, 0x7D, 0x53, track, 0xF7])

                elif msg_type == "clip_stop_all":
                    midi_out.send_message([0xF0, 0x7D, 0x54, 0x00, 0xF7])

                elif msg_type == "song_activate":
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
async def watch_state_file():
    """Watch /tmp/liverig_state.json written by M4L JS."""
    import os
    last_mtime = 0
    last_content = ""
    poll_count = 0
    change_count = 0
    error_count = 0
    print(f"[LiveRig] Watching /tmp/liverig_state.json", flush=True)
    while True:
        poll_count += 1
        try:
            mtime = os.path.getmtime("/tmp/liverig_state.json")
            if mtime != last_mtime:
                last_mtime = mtime
                with open("/tmp/liverig_state.json", 'r') as fh:
                    content = fh.read().strip()
                if content and content != last_content:
                    last_content = content
                    try:
                        msg = json.loads(content)
                    except Exception as e:
                        error_count += 1
                        if error_count < 5:
                            print(f"[LiveRig] JSON parse fail: {e} | content: {content[:100]}", flush=True)
                        continue
                    changed = False
                    for k, v in msg.items():
                        if live_state.get(k) != v:
                            live_state[k] = v
                            changed = True
                    live_state["type"] = "live_state"
                    if changed:
                        change_count += 1
                        await broadcast_live_state()
                        if change_count == 1 or change_count % 20 == 0:
                            print(f"[LiveRig] ✓#{change_count} bpm={live_state.get('bpm')} {live_state.get('transport')} bar={live_state.get('bar')} beat={live_state.get('beat')}", flush=True)
        except FileNotFoundError:
            if poll_count % 100 == 0:
                print(f"[LiveRig] state file not found yet (poll #{poll_count})", flush=True)
        except Exception as e:
            error_count += 1
            if error_count < 5:
                print(f"[LiveRig] watch error: {e}", flush=True)
        await asyncio.sleep(0.05)

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    load_fader_names()
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

    # Start file watcher for M4L JS state file
    asyncio.create_task(watch_state_file())

    # Start HTTP server for M4L JS → bridge
    http_server = await asyncio.start_server(handle_http, "127.0.0.1", 9090)
    print(f"[LiveRig] HTTP receiver ready on 127.0.0.1:9090", flush=True)

    # Start UDP listener on loopback — Max udpsend sends to 127.0.0.1
    await main_loop.create_datagram_endpoint(
        UDPProtocol,
        local_addr=("127.0.0.1", UDP_PORT)
    )
    print(f"[LiveRig] UDP listener ready on 127.0.0.1:{UDP_PORT}", flush=True)

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
