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

# ── 4. Detect hostname ────────────────────────────────────────────────────────
MDNS_HOST=$(scutil --get LocalHostName 2>/dev/null)
if [ -n "$MDNS_HOST" ]; then
    BRIDGE_HOST="${MDNS_HOST}.local"
else
    BRIDGE_HOST=$(ifconfig 2>/dev/null | grep "inet 169.254" | awk '{print $2}' | head -1)
    [ -z "$BRIDGE_HOST" ] && BRIDGE_HOST=$(ifconfig 2>/dev/null | grep "inet 172.20" | awk '{print $2}' | head -1)
    [ -z "$BRIDGE_HOST" ] && BRIDGE_HOST=$(ipconfig getifaddr en0 2>/dev/null)
    [ -z "$BRIDGE_HOST" ] && BRIDGE_HOST="NOT_DETECTED"
fi

# ── 5. Inject hostname into HTML and serve it ─────────────────────────────────
sed "s|{{BRIDGE_HOST}}|$BRIDGE_HOST|g" "$HTML_SRC" > "$HTML_SERVED"

# Start HTTP server from /tmp
cd /tmp
$PYTHON -m http.server $HTTP_PORT > "$HTTP_LOG" 2>&1 &
HTTP_PID=$!
echo $HTTP_PID > "$HTTP_PID_FILE"
sleep 1

if ! kill -0 $HTTP_PID 2>/dev/null; then
    fatal "HTTP server failed to start."
fi

# ── 6. Build URL and notify ───────────────────────────────────────────────────
IPAD_URL="http://$BRIDGE_HOST:$HTTP_PORT/liverig_controller_served.html"
echo -n "$IPAD_URL" | pbcopy 2>/dev/null
notify "Bridge running · $BRIDGE_HOST (copied)" "Glass"


osascript << EOF
display dialog "✅  LiveRig Bridge is running.

Open this URL in Safari on your iPad:

$IPAD_URL

(already copied to clipboard)

💡 This URL never changes — bookmark it or
   Add to Home Screen for instant access every time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
iPad setup:
  1. iPad plugged into Mac via USB
  2. Personal Hotspot ON on iPad

Ableton setup (one time only):
  Preferences › MIDI › Input  'LiveRig Bridge'
    → Track ON   Remote ON
  Preferences › MIDI › Output 'LiveRig Bridge'
    → Track ON   Remote ON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" buttons {"Stop Bridge"} default button "Stop Bridge" with title "LiveRig Bridge — Running"
EOF

# ── 8. Stop everything ───────────────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE"
[ -f "$HTTP_PID_FILE" ] && kill "$(cat "$HTTP_PID_FILE")" 2>/dev/null && rm -f "$HTTP_PID_FILE"
notify "Bridge stopped." "Funk"
