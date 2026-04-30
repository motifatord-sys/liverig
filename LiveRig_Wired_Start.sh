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
LAUNCHER_LOG="/tmp/liverig_launcher.log"
PID_FILE="/tmp/liverig_bridge.pid"
HTTP_PID_FILE="/tmp/liverig_http.pid"
HTTP_PORT=8080

# Mirror everything to a debug log file
exec > >(tee "$LAUNCHER_LOG") 2>&1

echo "[$(date)] LiveRig launcher starting..."
echo "SCRIPT_DIR=$SCRIPT_DIR"
echo "BRIDGE=$BRIDGE"
echo "HTML_SRC=$HTML_SRC"

notify() { osascript -e "display notification \"$1\" with title \"LiveRig Bridge\" sound name \"${2:-Basso}\"" 2>/dev/null; }
fatal() {
    notify "$1"
    echo "ERROR: $1"
    osascript -e "display dialog \"$1\n\nLog: $LAUNCHER_LOG\" buttons {\"OK\"} default button \"OK\" with title \"LiveRig Bridge — Error\"" 2>/dev/null
    exit 1
}

# ── 0. Checks ────────────────────────────────────────────────────────────────
[ ! -f "$BRIDGE" ] && fatal "liverig_bridge_wired.py not found next to this script. Looked in: $SCRIPT_DIR"
[ ! -f "$HTML_SRC" ] && fatal "live_rig_3_controller.html not found next to this script. Looked in: $SCRIPT_DIR"

# ── 1. Python detection — prefer a Python with tkinter ───────────────────────
PYTHON=""
TK_TEST="import tkinter; tkinter.Tk().destroy()"

# Priority 1: virtual env (if it has tkinter)
if [ -f "$HOME/liverig-env/bin/python" ]; then
    if "$HOME/liverig-env/bin/python" -c "$TK_TEST" 2>/dev/null; then
        PYTHON="$HOME/liverig-env/bin/python"
        echo "Using venv Python: $PYTHON (tkinter OK)"
    else
        echo "venv Python lacks tkinter, trying others..."
    fi
fi

# Priority 2: Homebrew python3 (most likely to have tkinter)
if [ -z "$PYTHON" ]; then
    for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            if "$cand" -c "$TK_TEST" 2>/dev/null; then
                PYTHON="$cand"
                echo "Using Python: $PYTHON (tkinter OK)"
                break
            fi
        fi
    done
fi

# Priority 3: any python3 even without tkinter (we'll fall back to osascript)
if [ -z "$PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
        TK_AVAILABLE=0
        echo "WARNING: Using Python without tkinter — falling back to osascript dialog"
    else
        fatal "Python 3 not found. Install via Homebrew: brew install python3"
    fi
else
    TK_AVAILABLE=1
fi

# ── 2. Kill existing instances ───────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE" && sleep 0.3
[ -f "$HTTP_PID_FILE" ] && kill "$(cat "$HTTP_PID_FILE")" 2>/dev/null && rm -f "$HTTP_PID_FILE" && sleep 0.3
EXISTING=$(lsof -ti tcp:8765 2>/dev/null); [ -n "$EXISTING" ] && kill $EXISTING 2>/dev/null && sleep 0.3
EXISTING=$(lsof -ti tcp:$HTTP_PORT 2>/dev/null); [ -n "$EXISTING" ] && kill $EXISTING 2>/dev/null && sleep 0.3

# ── 3. Start MIDI bridge ─────────────────────────────────────────────────────
echo "Starting bridge: $PYTHON $BRIDGE"
"$PYTHON" "$BRIDGE" > "$LOG" 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > "$PID_FILE"
sleep 2

if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    LAST_LINE=$(tail -5 "$LOG" 2>/dev/null)
    fatal "Bridge failed to start.\n\n$LAST_LINE\n\nFull log: $LOG"
fi
echo "Bridge running (PID $BRIDGE_PID)"

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
echo "BRIDGE_HOST=$BRIDGE_HOST"

# ── 5. Inject hostname into HTML and serve it ─────────────────────────────────
sed "s|{{BRIDGE_HOST}}|$BRIDGE_HOST|g" "$HTML_SRC" > "$HTML_SERVED"

cd /tmp
"$PYTHON" -m http.server $HTTP_PORT > "$HTTP_LOG" 2>&1 &
HTTP_PID=$!
echo $HTTP_PID > "$HTTP_PID_FILE"
sleep 1

if ! kill -0 $HTTP_PID 2>/dev/null; then
    fatal "HTTP server failed to start."
fi
echo "HTTP server running (PID $HTTP_PID)"

# ── 6. Build URL and notify ───────────────────────────────────────────────────
IPAD_URL="http://$BRIDGE_HOST:$HTTP_PORT/liverig_controller_served.html"
echo -n "$IPAD_URL" | pbcopy 2>/dev/null
notify "Bridge running · $BRIDGE_HOST (copied)" "Glass"

# ── 7. Show window ───────────────────────────────────────────────────────────
if [ "$TK_AVAILABLE" = "1" ]; then
    # Tkinter path — minimizable window
    cat > /tmp/liverig_window.py << PYEOF
import tkinter as tk
import os, signal, sys

IPAD_URL = os.environ.get("LIVERIG_URL", "")

def stop_and_exit():
    for pf in ("/tmp/liverig_bridge.pid", "/tmp/liverig_http.pid"):
        try:
            with open(pf) as f:
                pid = int(f.read().strip())
            try: os.kill(pid, signal.SIGTERM)
            except Exception: pass
            try: os.remove(pf)
            except Exception: pass
        except Exception:
            pass
    os.system('osascript -e \'display notification "Bridge stopped." with title "LiveRig Bridge" sound name "Funk"\' 2>/dev/null')
    try: root.destroy()
    except Exception: pass
    sys.exit(0)

root = tk.Tk()
root.title("LiveRig Bridge")
root.geometry("520x520")
root.configure(bg="#1a1a1f")
root.lift()
root.after(150, lambda: root.attributes('-topmost', False))

frm = tk.Frame(root, bg="#1a1a1f", padx=20, pady=20)
frm.pack(fill="both", expand=True)

tk.Label(frm, text=u"\u2705  LiveRig Bridge is running",
         font=("Helvetica", 16, "bold"), bg="#1a1a1f", fg="#5ed06f").pack(anchor="w", pady=(0,10))
tk.Label(frm, text="Open this URL in Safari on your iPad:",
         font=("Helvetica", 11), bg="#1a1a1f", fg="#cccccc").pack(anchor="w")

url_entry = tk.Text(frm, height=2, width=58, bg="#0d0d10", fg="#7ac8ff",
                    font=("Menlo", 11), relief="flat", padx=8, pady=6, wrap="word")
url_entry.insert("1.0", IPAD_URL)
url_entry.configure(state="disabled")
url_entry.pack(anchor="w", fill="x", pady=(4, 4))

tk.Label(frm, text="(already copied to clipboard)",
         font=("Helvetica", 10, "italic"), bg="#1a1a1f", fg="#888").pack(anchor="w", pady=(0, 12))

tk.Label(frm, text=u"\U0001F4A1  This URL never changes \u2014 bookmark it or\n     Add to Home Screen for instant access.",
         font=("Helvetica", 11), bg="#1a1a1f", fg="#aaa", justify="left").pack(anchor="w", pady=(0, 12))

tk.Frame(frm, bg="#3a3a45", height=1).pack(fill="x", pady=8)

tk.Label(frm, text="iPad setup",
         font=("Helvetica", 11, "bold"), bg="#1a1a1f", fg="#fff").pack(anchor="w")
tk.Label(frm, text="  1. iPad plugged into Mac via USB\n  2. Personal Hotspot ON on iPad",
         font=("Menlo", 10), bg="#1a1a1f", fg="#bbb", justify="left").pack(anchor="w", pady=(2, 10))

tk.Label(frm, text="Ableton setup (one time only)",
         font=("Helvetica", 11, "bold"), bg="#1a1a1f", fg="#fff").pack(anchor="w")
tk.Label(frm,
         text="  Preferences > MIDI > Input  'LiveRig Bridge'\n    -> Track ON   Remote ON\n  Preferences > MIDI > Output 'LiveRig Bridge'\n    -> Track ON   Remote ON",
         font=("Menlo", 10), bg="#1a1a1f", fg="#bbb", justify="left").pack(anchor="w", pady=(2, 16))

btn_frame = tk.Frame(frm, bg="#1a1a1f")
btn_frame.pack(side="bottom", fill="x")
tk.Button(btn_frame, text="Stop Bridge", font=("Helvetica", 13, "bold"),
          bg="#7a1010", fg="#ffaaaa",
          activebackground="#a02020", activeforeground="#fff",
          relief="flat", padx=20, pady=10, cursor="hand2",
          command=stop_and_exit).pack(side="right")
tk.Button(btn_frame, text="Minimize", font=("Helvetica", 12),
          bg="#2a2a35", fg="#ccc",
          activebackground="#3a3a48", activeforeground="#fff",
          relief="flat", padx=15, pady=10, cursor="hand2",
          command=lambda: root.iconify()).pack(side="right", padx=(0, 8))

root.protocol("WM_DELETE_WINDOW", stop_and_exit)
root.bind("<Command-w>", lambda e: stop_and_exit())
root.bind("<Command-h>", lambda e: root.iconify())
root.bind("<Command-m>", lambda e: root.iconify())

root.mainloop()
PYEOF
    LIVERIG_URL="$IPAD_URL" "$PYTHON" /tmp/liverig_window.py
else
    # Fallback: legacy modal dialog (modal but at least it works)
    osascript << EOA
display dialog "LiveRig Bridge is running.

Open this URL in Safari on your iPad:

$IPAD_URL

(already copied to clipboard)

iPad setup:
  1. iPad plugged into Mac via USB
  2. Personal Hotspot ON on iPad

Ableton setup (one time only):
  Preferences > MIDI > Input  'LiveRig Bridge'
    -> Track ON   Remote ON
  Preferences > MIDI > Output 'LiveRig Bridge'
    -> Track ON   Remote ON

Note: This dialog is modal because tkinter is not installed.
To get a minimizable window, install Homebrew Python: brew install python-tk python3" buttons {"Stop Bridge"} default button "Stop Bridge" with title "LiveRig Bridge"
EOA
fi

# ── 8. Stop everything ───────────────────────────────────────────────────────
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE"
[ -f "$HTTP_PID_FILE" ] && kill "$(cat "$HTTP_PID_FILE")" 2>/dev/null && rm -f "$HTTP_PID_FILE"
notify "Bridge stopped." "Funk"
echo "[$(date)] Launcher exiting cleanly."
