#!/usr/bin/env python3
"""
LiveRig MIDI Bridge  (v4 — bidirectional MIDI/SysEx + lighting OSC out)
Runs on your Mac. The iPad connects wirelessly over the local network
(Safari -> this bridge's WebSocket server). All Ableton state flows through
the Remote Script's SysEx feedback -- the old Max-for-Live inputs (UDP:9000,
HTTP:9090, /tmp/liverig_state.json file watcher) were removed 2026-07-06
after sitting dead since the Remote Script migration.
Requirements: pip install python-rtmidi websockets
"""

import asyncio, json, os, struct, sys, socket, subprocess, threading, time
from urllib.parse import urlparse, parse_qs

WS_PORT  = 8765
MIDI_PORT_NAME = "LiveRig Bridge"

# Version handshake (2026-07-06): the same LIVERIG_VERSION string lives in
# LiveRig.py, liverig_bridge_wired.py, and live_rig_3_controller.html. Each
# component reports its copy at connect time and the iPad shows a red VER
# badge if they disagree. Bump ALL THREE together on every deploy;
# scripts/deploy.sh verifies they match.
LIVERIG_VERSION = "2026.07.06.5"

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

# NOTE (2026-07-06): the old `live_state` dict (fake "Track 1..8" defaults,
# fed by the retired M4L UDP/HTTP/file-watcher inputs) is gone. All Ableton
# state reaches the iPad via the Remote Script's SysEx feedback, re-requested
# on every connect via SX_REQUEST_FULL_STATE (0x4A) below. The HTML's
# onLiveState() handler remains, harmlessly dormant.

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

# ── Patch snapshots + song names (portable across iPads, 2026-07-06) ─────────
# Same pattern as kbd_fader_names above: the Patches page's captured snapshots
# (fader/button states per song) and custom song names used to live only in
# each iPad's localStorage -- a swapped/reset iPad mid-tour lost the whole
# patch library. Now persisted on the Mac, pushed to every client on connect,
# rebroadcast to all clients on change.
SNAPSHOTS_FILE = os.path.expanduser(
    "~/Library/Application Support/LiveRig/patch_snapshots.json")
patch_snapshots = {"snapshots": [], "songNames": []}

def load_patch_snapshots():
    global patch_snapshots
    try:
        with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            patch_snapshots = {
                "snapshots": d.get("snapshots") if isinstance(d.get("snapshots"), list) else [],
                "songNames": d.get("songNames") if isinstance(d.get("songNames"), list) else [],
            }
            n = sum(1 for s in patch_snapshots["snapshots"]
                    if isinstance(s, dict) and s)
            print(f"[LiveRig] loaded {n} patch snapshot(s)", flush=True)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[LiveRig] snapshots load failed: {e}", flush=True)

def save_patch_snapshots():
    try:
        os.makedirs(os.path.dirname(SNAPSHOTS_FILE), exist_ok=True)
        with open(SNAPSHOTS_FILE, "w", encoding="utf-8") as fh:
            json.dump(patch_snapshots, fh)
    except Exception as e:
        print(f"[LiveRig] snapshots save failed: {e}", flush=True)

# ── Lighting OSC cues from song sections (2026-07-06) ─────────────────────────
# The Remote Script already reports which MARKERS-track section the playhead is
# in (FB_MARKER_ITEM 0x57 = the ordered section list, FB_MARKER_NOW 0x58 =
# current section + progress, ~10 Hz while playing -- the same data that drives
# the Transport section strip). This block turns that into lighting control:
# on every section CHANGE the bridge fires OSC to a console/software on the
# network, so lighting looks follow the song automatically -- and because it
# follows the playhead through named sections (not timecode), it tracks live
# arrangement changes: vamp a chorus, jump a locator, lights follow.
#
# Configured via a new optional top-level "lighting" key in rig_config.json:
#   "lighting": {
#     "enabled": true,
#     "oscHost": "10.0.0.50",          // console/software IP
#     "oscPort": 8000,
#     "sendSectionName": true,          // /liverig/section <name> <index> on change
#     "sendProgress": false,            // /liverig/progress <0.0-1.0> (~10 Hz, for fades)
#     "cues": {                         // optional per-section console-specific messages
#       "CHORUS": "/cue/12/fire",                            // address only
#       "VERSE 1": {"address": "/eos/cue/1/11/fire", "args": []}  // with args (int/float/str)
#     }
#   }
# Section-name matching is case-insensitive (same rule as track binding).
# Everything here fails SILENTLY toward the music side: no console listening,
# bad host, missing config -- the worst case is a log line, never a crash.
#
# The OSC encoder is hand-rolled (~20 lines) rather than a pip dependency ON
# PURPOSE: the app's _ensure_bridge_venv() only installs packages on first
# run, so a new import would crash every already-provisioned rig until a
# manual venv rebuild. stdlib-only code has no such failure mode.

def osc_message(address, *args):
    """Encode one OSC message (address + typed args). Supports int (i),
    float (f), str (s) -- the types lighting consoles actually use."""
    def pad_str(s):
        b = s.encode("utf-8") + b"\x00"
        return b + b"\x00" * ((4 - len(b) % 4) % 4)
    tags, payload = ",", b""
    for a in args:
        if isinstance(a, bool):
            tags += "T" if a else "F"
        elif isinstance(a, int):
            tags += "i"; payload += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"; payload += struct.pack(">f", a)
        else:
            tags += "s"; payload += pad_str(str(a))
    return pad_str(address) + pad_str(tags) + payload

LIGHTING = {"enabled": False}
_osc_sock = None
_osc_err_logged = False

def load_lighting_config():
    """Read the optional "lighting" section from rig_config.json. Tries the
    Desktop repo copy first (canonical), then the served www copy."""
    global LIGHTING, _osc_sock
    cfg = None
    for p in (os.path.expanduser("~/Desktop/liverig/rig_config.json"),
              os.path.expanduser(
                  "~/Library/Application Support/LiveRig/rig_config.json"),
              "/private/tmp/liverig_www/rig_config.json"):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
            break
        except Exception:
            continue
    lit = (cfg or {}).get("lighting")
    if not isinstance(lit, dict) or not lit.get("enabled"):
        LIGHTING = {"enabled": False}
        return
    cues = {}
    for k, v in (lit.get("cues") or {}).items():
        key = str(k).strip().lower()
        if isinstance(v, str) and v.strip():
            cues[key] = {"address": v.strip(), "args": []}
        elif isinstance(v, dict) and v.get("address"):
            args = [a for a in (v.get("args") or [])
                    if isinstance(a, (int, float, str, bool))]
            cues[key] = {"address": str(v["address"]), "args": args}
    LIGHTING = {
        "enabled": True,
        "host": str(lit.get("oscHost", "127.0.0.1")),
        "port": int(lit.get("oscPort", 8000)),
        "sendSectionName": bool(lit.get("sendSectionName", True)),
        "sendProgress": bool(lit.get("sendProgress", False)),
        "cues": cues,
    }
    try:
        _osc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except Exception as e:
        print(f"[LiveRig] lighting: socket failed: {e}", flush=True)
        LIGHTING = {"enabled": False}
        return
    print(f"[LiveRig] lighting OSC -> {LIGHTING['host']}:{LIGHTING['port']} "
          f"({len(cues)} cue mapping(s), progress "
          f"{'on' if LIGHTING['sendProgress'] else 'off'})", flush=True)

def _osc_send(address, *args):
    global _osc_err_logged
    if not LIGHTING.get("enabled") or _osc_sock is None:
        return
    try:
        _osc_sock.sendto(osc_message(address, *args),
                         (LIGHTING["host"], LIGHTING["port"]))
    except Exception as e:
        if not _osc_err_logged:   # log once, never spam at 10 Hz
            _osc_err_logged = True
            print(f"[LiveRig] lighting: OSC send failed: {e}", flush=True)

# Section state, rebuilt from the Remote Script's own marker feedback.
marker_names = {}            # idx -> section name (from FB_MARKER_ITEM)
current_section_idx = None   # None = unknown since startup; -1 = outside all

def handle_marker_feedback(fb, data):
    """Track marker list + current section; fire OSC on section change."""
    global current_section_idx
    if fb == 0x57 and len(data) >= 3:            # FB_MARKER_ITEM
        idx, ln = data[1], data[2]
        if idx == 0:
            marker_names.clear()                 # new list starting over
        marker_names[idx] = "".join(chr(b & 0x7F) for b in data[3:3 + ln])
    elif fb == 0x58 and len(data) >= 3:          # FB_MARKER_NOW
        raw = data[0]
        idx = -1 if raw == 0x7F else raw
        prog = (((data[1] & 0x7F) << 7) | (data[2] & 0x7F)) / 0x3FFF
        if idx != current_section_idx:
            current_section_idx = idx
            name = marker_names.get(idx, "") if idx >= 0 else ""
            if LIGHTING.get("sendSectionName", True):
                _osc_send("/liverig/section", name, idx)
            cue = LIGHTING.get("cues", {}).get(name.strip().lower())
            if cue:
                _osc_send(cue["address"], *cue["args"])
            print(f"[LiveRig] lighting: section -> "
                  f"{name or '(none)'} [{idx}]"
                  + (f" cue {cue['address']}" if cue else ""), flush=True)
        if LIGHTING.get("sendProgress"):
            _osc_send("/liverig/progress", float(prog))

def maybe_handle_lighting(midi_bytes):
    """Peek at Remote Script SysEx feedback for the two marker codes.
    Called from the rtmidi callback thread; must never raise."""
    try:
        if (LIGHTING.get("enabled") and len(midi_bytes) >= 6
                and midi_bytes[0] == 0xF0 and midi_bytes[1] == 0x7D
                and midi_bytes[2] == 0x60 and midi_bytes[3] in (0x57, 0x58)):
            handle_marker_feedback(midi_bytes[3], list(midi_bytes[4:-1]))
    except Exception as e:
        print(f"[LiveRig] lighting: parse error: {e}", flush=True)

# ── MIDI IN callback (Ableton → iPad) ────────────────────────────────────────
def midi_in_callback(message, data=None):
    global rx_count
    midi_bytes, _ = message
    if not midi_bytes:
        return
    rx_count += 1
    maybe_handle_lighting(midi_bytes)   # OSC section cues; never raises
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
    # Version handshake: tell this client which bridge version it's talking
    # to, so the UI can flag a stale deploy (see LIVERIG_VERSION note above).
    try:
        await websocket.send(json.dumps(
            {"type": "bridge_version", "version": LIVERIG_VERSION}))
    except Exception as e:
        print(f"[LiveRig] version send failed: {e}", flush=True)
    # Push the portable KBD fader names so this client matches every other one.
    try:
        await websocket.send(json.dumps({"type": "kbd_fader_names", "names": kbd_fader_names}))
    except Exception as e:
        print(f"[LiveRig] fader-names send failed: {e}", flush=True)
    # Push the portable patch snapshots + song names (same portability
    # pattern as fader names -- see SNAPSHOTS_FILE comment above).
    try:
        await websocket.send(json.dumps({"type": "patch_snapshots",
                                         "snapshots": patch_snapshots["snapshots"],
                                         "songNames": patch_snapshots["songNames"]}))
    except Exception as e:
        print(f"[LiveRig] snapshots send failed: {e}", flush=True)
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

                elif msg_type == "set_patch_snapshots":
                    # An iPad captured/renamed a patch. Persist and rebroadcast
                    # the full set so every connected iPad stays in sync.
                    snaps = data.get("snapshots")
                    names = data.get("songNames")
                    if isinstance(snaps, list):
                        patch_snapshots["snapshots"] = snaps
                        if isinstance(names, list):
                            patch_snapshots["songNames"] = names
                        save_patch_snapshots()
                        await broadcast(json.dumps(
                            {"type": "patch_snapshots",
                             "snapshots": patch_snapshots["snapshots"],
                             "songNames": patch_snapshots["songNames"]}))

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
async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    load_fader_names()
    load_patch_snapshots()
    load_lighting_config()
    ips = get_all_ips()
    print(f"\n{'='*58}")
    print(f"  LiveRig MIDI Bridge  (v4, {LIVERIG_VERSION})")
    print(f"{'='*58}")
    print(f"\n  Virtual MIDI ports: '{MIDI_PORT_NAME}'")
    print(f"\n  Ableton Preferences > MIDI:")
    print(f"    Input  '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"    Output '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"\n  Network interfaces:")
    for iface, ip in ips.items():
        print(f"    {iface:22s} {ip}")
    print(f"\n  WebSocket : 0.0.0.0:{WS_PORT}")
    print(f"{'='*58}\n")

    # WebSocket server (the bridge's only inbound channel since the M4L
    # UDP/HTTP/file-watcher inputs were removed 2026-07-06)
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
