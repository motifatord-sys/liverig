#!/bin/bash
# ╔══════════════════════════════════════════════════════╗
# ║   LiveRig Bridge — Wired USB Launcher                ║
# ║   Double-click this file to start everything.        ║
# ╚══════════════════════════════════════════════════════╝

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BRIDGE="$SCRIPT_DIR/liverig_bridge_wired.py"
HTML_SRC="$SCRIPT_DIR/live_rig_3_controller.html"
HTML_SERVED="/tmp/liverig_controller_served.html"
LOG="/tmp/liverig_bridge.log"
HTTP_LOG="/tmp/liverig_http.log"
PID_FILE="/tmp/liverig_bridge.pid"
HTTP_PID_FILE="/tmp/liverig_http.pid"
HTTP_PORT=8080

notify() { osascript -e "display notification \"$1\" with title \"LiveRig Bridge\" sound name \"${2:-Basso}\"" 2>/dev/null; }
fatal() { notify "$1"; echo "ERROR: $1"; exit 1; }

# ── 0. Checks ────────────────────────────────────────────────────────────────
[ ! -f "$BRIDGE" ] && fatal "liverig_bridge_wired.py not found next to this script."
[ ! -f "$HTML_SRC" ] && fatal "live_rig_3_controller.html not found next to this script."

# ── 1. Python ────────────────────────────────────────────────────────────────
if [ -f "$HOME/liverig-env/bin/python" ]; then
    PYTHON="$HOME/liverig-env/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    fatal "Python 3 not found. Install via Homebrew: brew install python3"
fi

# ── 2. Kill existing instances ───────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE" && sleep 0.3
[ -f "$HTTP_PID_FILE" ] && kill "$(cat "$HTTP_PID_FILE")" 2>/dev/null && rm -f "$HTTP_PID_FILE" && sleep 0.3
EXISTING=$(lsof -ti tcp:8765 2>/dev/null); [ -n "$EXISTING" ] && kill $EXISTING 2>/dev/null && sleep 0.3
EXISTING=$(lsof -ti tcp:$HTTP_PORT 2>/dev/null); [ -n "$EXISTING" ] && kill $EXISTING 2>/dev/null && sleep 0.3

# ── 3. Start MIDI bridge ─────────────────────────────────────────────────────
$PYTHON "$BRIDGE" > "$LOG" 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > "$PID_FILE"
sleep 2

if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    LAST_LINE=$(tail -3 "$LOG" 2>/dev/null)
    osascript -e "display dialog \"Bridge failed to start.\n\n$LAST_LINE\n\nFull log: $LOG\" buttons {\"OK\"} default button \"OK\" with title \"LiveRig Bridge — Error\""
    exit 1
fi

# ── 4. Detect USB IP ─────────────────────────────────────────────────────────
sleep 1
USB_IP=$(ifconfig 2>/dev/null | grep "inet 169.254" | awk '{print $2}' | head -1)
[ -z "$USB_IP" ] && USB_IP=$(ifconfig 2>/dev/null | grep "inet 172.20" | awk '{print $2}' | head -1)
[ -z "$USB_IP" ] && USB_IP=$(ifconfig 2>/dev/null | grep -A3 -i "iphone\|ipad\|usb" | grep "inet " | awk '{print $2}' | head -1)
[ -z "$USB_IP" ] && USB_IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$USB_IP" ] && USB_IP="NOT_DETECTED"

# ── 5. Inject IP into HTML and serve it ──────────────────────────────────────
# Inject the detected IP into the HTML placeholder
sed "s|{{BRIDGE_IP}}|$USB_IP|g" "$HTML_SRC" > "$HTML_SERVED"

# Start HTTP server from /tmp so it serves the modified HTML
cd /tmp
$PYTHON -m http.server $HTTP_PORT > "$HTTP_LOG" 2>&1 &
HTTP_PID=$!
echo $HTTP_PID > "$HTTP_PID_FILE"
sleep 1

if ! kill -0 $HTTP_PID 2>/dev/null; then
    fatal "HTTP server failed to start."
fi

# ── 6. Copy IP and notify ─────────────────────────────────────────────────────
echo -n "$USB_IP" | pbcopy 2>/dev/null
notify "Bridge running · $USB_IP (copied)" "Glass"

IPAD_URL="http://$USB_IP:$HTTP_PORT/liverig_controller_served.html"

# ── 7. Show dialog ───────────────────────────────────────────────────────────
# ── 7. Show dialog ───────────────────────────────────────────────────────────
# Copy URL to clipboard upfront so it's ready before user even clicks
echo -n "$IPAD_URL" | pbcopy 2>/dev/null

osascript << EOF
display dialog "✅  LiveRig Bridge is running.

On your iPad open Safari and go to:

$IPAD_URL

(URL already copied to clipboard)

The controller will load and connect automatically.
Bookmark it or Add to Home Screen for next time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
iPad checklist:
  1. Plugged into Mac via USB cable
  2. Personal Hotspot ON on iPad

Ableton checklist:
  • Preferences › MIDI › Input  'LiveRig Bridge' → Track ✓  Remote ✓
  • Preferences › MIDI › Output 'LiveRig Bridge' → Track ✓  Remote ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" buttons {"Stop Bridge"} default button "Stop Bridge" with title "LiveRig Bridge — Running"
EOF

# ── 8. Stop everything ───────────────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE"
[ -f "$HTTP_PID_FILE" ] && kill "$(cat "$HTTP_PID_FILE")" 2>/dev/null && rm -f "$HTTP_PID_FILE"
notify "Bridge stopped." "Funk"
