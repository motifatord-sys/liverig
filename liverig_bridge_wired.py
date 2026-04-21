#!/usr/bin/env python3
"""
LiveRig MIDI Bridge — Wired USB Edition  (v2 — bidirectional)
Runs on your Mac. iPad connects via USB cable only.
Requirements: pip install python-rtmidi websockets
"""

import asyncio, json, sys, socket, subprocess, threading, time

WS_PORT = 8765
MIDI_PORT_NAME = "LiveRig Bridge"

try:
    import rtmidi
except ImportError:
    print("ERROR: pip install python-rtmidi")
    sys.exit(1)

try:
    import websockets
    try:
        from websockets.asyncio.server import serve as ws_serve
    except ImportError:
        from websockets.legacy.server import serve as ws_serve
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

midi_out = rtmidi.MidiOut()
midi_out.open_virtual_port(MIDI_PORT_NAME)

midi_in = rtmidi.MidiIn()
midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
midi_in.open_virtual_port(MIDI_PORT_NAME)

clients = set()
clients_lock = asyncio.Lock()
main_loop = None
rx_count = 0
tx_count = 0

def midi_in_callback(message, data=None):
    global rx_count
    midi_bytes, delta_time = message
    if not midi_bytes:
        return
    rx_count += 1
    if rx_count % 50 == 0:
        print(f"[LiveRig] <- {rx_count} msgs from Ableton", flush=True)
    payload = json.dumps(list(midi_bytes))
    async def _broadcast():
        async with clients_lock:
            dead = set()
            for ws in clients:
                try:
                    await ws.send(payload)
                except Exception:
                    dead.add(ws)
            clients.difference_update(dead)
    if main_loop and not main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(), main_loop)

midi_in.set_callback(midi_in_callback)

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

async def handle_client(websocket, path=None):
    global tx_count
    try:
        ip = websocket.remote_address[0]
    except Exception:
        ip = "unknown"
    print(f"[LiveRig] iPad connected from {ip}", flush=True)
    async with clients_lock:
        clients.add(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message) if isinstance(message, str) else list(message)
                if isinstance(data, list) and data:
                    midi_out.send_message([int(b) & 0xFF for b in data])
                    tx_count += 1
                    if tx_count % 100 == 0:
                        print(f"[LiveRig] -> {tx_count} msgs to Ableton", flush=True)
            except Exception as e:
                print(f"[LiveRig] Bad message: {e}", flush=True)
    except Exception:
        pass
    finally:
        async with clients_lock:
            clients.discard(websocket)
        print(f"[LiveRig] iPad disconnected ({ip})", flush=True)

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    ips = get_all_ips()
    print(f"\n{'='*56}")
    print(f"  LiveRig MIDI Bridge — Wired USB Mode  (v2 bidir)")
    print(f"{'='*56}")
    print(f"\n  Virtual MIDI ports (IN + OUT): '{MIDI_PORT_NAME}'")
    print(f"\n  Ableton Preferences > MIDI:")
    print(f"    Input  '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"    Output '{MIDI_PORT_NAME}' -> Track ON, Remote ON")
    print(f"\n  Network interfaces detected:")
    usb_ip = None
    for iface, ip in ips.items():
        label = ""
        if ip.startswith("169.254"):
            label = "  <-- USB link-local (use this)"
            if usb_ip is None:
                usb_ip = ip
        elif any(k in iface.lower() for k in ("iphone", "ipad", "usb")):
            label = "  <-- USB interface"
            if usb_ip is None:
                usb_ip = ip
        print(f"    {iface:22s} {ip}{label}")
    if usb_ip:
        print(f"\n  Enter in Live Rig on iPad: {usb_ip}")
    else:
        print(f"\n  USB IP not detected. Using WiFi for now.")
    print(f"\n  Listening on 0.0.0.0:{WS_PORT}  (bidir MIDI ready)")
    print(f"{'='*56}\n")
    async with ws_serve(handle_client, "0.0.0.0", WS_PORT):
        await asyncio.Future()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n[LiveRig] Stopped.")
finally:
    midi_in.close_port()
    midi_out.close_port()
