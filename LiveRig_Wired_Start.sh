#!/bin/bash
# ╔══════════════════════════════════════════════════════╗
# ║   LiveRig Bridge — Wired USB Launcher                ║
# ║   Double-click this file to start the bridge.        ║
# ╚══════════════════════════════════════════════════════╝

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BRIDGE="$SCRIPT_DIR/liverig_bridge_wired.py"
LOG="/tmp/liverig_bridge.log"
PID_FILE="/tmp/liverig_bridge.pid"

notify() { osascript -e "display notification \"$1\" with title \"LiveRig Bridge\" sound name \"${2:-Basso}\"" 2>/dev/null; }
fatal() { notify "$1"; echo "ERROR: $1"; exit 1; }

# ── 0. Ensure the bridge script exists ──────────────────────────────────────
[ ! -f "$BRIDGE" ] && fatal "liverig_bridge_wired.py not found next to this script."

# ── 1. Ensure Python 3 is available (install via Homebrew if needed) ────────
if ! command -v python3 &>/dev/null; then
  CHOICE=$(osascript << 'EOF'
display dialog "Python 3 is not installed.

LiveRig will install it automatically via Homebrew.
This takes 2–5 minutes and only happens once.

Click Install to continue." buttons {"Cancel", "Install"} default button "Install" with title "LiveRig — Python Required"
EOF
)
  echo "$CHOICE" | grep -q "Cancel" && exit 0

  if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)"
    eval "$(/usr/local/bin/brew shellenv 2>/dev/null)"
  fi

  command -v brew &>/dev/null || fatal "Homebrew install failed. Install Python 3 from python.org then try again."

  echo "Installing Python 3..."
  brew install python3
  command -v python3 &>/dev/null || fatal "Python 3 install failed. Install from python.org then try again."
  notify "Python 3 installed!" "Glass"
fi

# ── 2. Install Python dependencies (silent, only if missing) ────────────────
python3 -c "import rtmidi"     2>/dev/null || pip3 install python-rtmidi     --break-system-packages -q 2>/dev/null || pip3 install python-rtmidi -q
python3 -c "import websockets" 2>/dev/null || pip3 install websockets         --break-system-packages -q 2>/dev/null || pip3 install websockets -q
python3 -c "import rtmidi, websockets" 2>/dev/null || fatal "Failed to install Python packages. Check your internet connection."

# ── 3. Kill any existing bridge instance ────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE" && sleep 0.3
EXISTING=$(lsof -ti tcp:8765 2>/dev/null)
[ -n "$EXISTING" ] && kill $EXISTING 2>/dev/null && sleep 0.3

# ── 4. Start the bridge ──────────────────────────────────────────────────────
python3 "$BRIDGE" > "$LOG" 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > "$PID_FILE"
sleep 2

if ! kill -0 $BRIDGE_PID 2>/dev/null; then
  LAST_LINE=$(tail -3 "$LOG" 2>/dev/null)
  osascript -e "display dialog \"Bridge failed to start.\n\n$LAST_LINE\n\nFull log: $LOG\" buttons {\"OK\"} default button \"OK\" with title \"LiveRig Bridge — Error\""
  exit 1
fi

# ── 5. Detect USB/iPad IP ────────────────────────────────────────────────────
USB_IP=$(ifconfig 2>/dev/null | grep -A3 -i "iphone\|ipad\|usb" | grep "inet " | awk '{print $2}' | head -1)
[ -z "$USB_IP" ] && USB_IP=$(ifconfig 2>/dev/null | grep "inet 169.254" | awk '{print $2}' | head -1)
[ -z "$USB_IP" ] && USB_IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$USB_IP" ] && USB_IP="Not detected — plug in iPad first"
echo -n "$USB_IP" | pbcopy 2>/dev/null
notify "Bridge running · $USB_IP (copied)" "Glass"

# ── 6. Show running dialog ───────────────────────────────────────────────────
osascript << EOF
display dialog "✅  LiveRig Bridge is running.

Enter this IP in the Live Rig app on your iPad:

          $USB_IP
     (already copied to clipboard)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
iPad checklist:
  1. Plugged into Mac via USB cable
  2. Tapped 'Trust This Computer' on iPad
  3. Open live_rig_3_controller.html in Safari
  4. Tap the status bar → paste IP → connect

Ableton checklist:
  • Preferences › MIDI › Input  'LiveRig Bridge' → Track ✓  Remote ✓
  • Preferences › MIDI › Output 'LiveRig Bridge' → Track ✓  Remote ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" buttons {"Copy IP Again", "Stop Bridge"} default button "Stop Bridge" with title "LiveRig Bridge — Running"
EOF

echo -n "$USB_IP" | pbcopy 2>/dev/null

# ── 7. Stop ──────────────────────────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE"
notify "Bridge stopped." "Funk"
