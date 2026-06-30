#!/usr/bin/env python3
"""LiveRig Menu Bar App — background controller with native macOS menu bar icon."""
import rumps
import subprocess
import threading
import time
import os
import sys
from pathlib import Path

BRIDGE_LOG = "/private/tmp/liverig_bridge.log"
HTTP_LOG   = "/private/tmp/liverig_http.log"
PID_FILE   = "/private/tmp/liverig_bridge.pid"
HTTP_PID   = "/private/tmp/liverig_http.pid"
HTTP_PORT  = 8080
WS_PORT    = 8765


def _kill_port(port):
    r = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
    for pid in r.stdout.strip().split():
        subprocess.run(["kill", pid], capture_output=True)


class LiveRigMenu(rumps.App):
    def __init__(self, support_dir, bridge_host, ipad_url):
        super().__init__("🎹", quit_button=None)
        self.support = Path(support_dir)
        self.host    = bridge_host
        self.url     = ipad_url
        self.bridge  = None
        self.http    = None

        self._status = rumps.MenuItem("⏳ Starting…", callback=None)
        self.menu = [
            self._status,
            None,
            rumps.MenuItem("Open on iPad (Safari)",  callback=self.open_url),
            rumps.MenuItem("Copy iPad URL",           callback=self.copy_url),
            None,
            rumps.MenuItem("Stop LiveRig",            callback=self.stop),
        ]

        threading.Thread(target=self._boot, daemon=True).start()

    # ── Boot sequence (runs in background thread) ──────────────────────────────
    def _boot(self):
        # Kill leftover processes
        for p in [PID_FILE, HTTP_PID]:
            pf = Path(p)
            if pf.exists():
                try:
                    os.kill(int(pf.read_text().strip()), 15)
                    time.sleep(0.2)
                except Exception:
                    pass
                pf.unlink(missing_ok=True)
        _kill_port(WS_PORT)
        _kill_port(HTTP_PORT)
        time.sleep(0.3)

        python = str(self.support / "venv/bin/python")

        # Inject hostname into HTML → /tmp
        src  = str(self.support / "live_rig_3_controller.html")
        dest = "/private/tmp/liverig_controller_served.html"
        with open(dest, "w") as fh:
            subprocess.run(
                ["sed", f"s|{{{{BRIDGE_HOST}}}}|{self.host}|g", src],
                stdout=fh
            )

        # Start WebSocket bridge
        with open(BRIDGE_LOG, "w") as log:
            self.bridge = subprocess.Popen(
                [python, str(self.support / "liverig_bridge_wired.py")],
                stdout=log, stderr=log
            )
        Path(PID_FILE).write_text(str(self.bridge.pid))
        time.sleep(2)

        if self.bridge.poll() is not None:
            rumps.alert("LiveRig Error",
                        f"Bridge failed to start.\nSee log: {BRIDGE_LOG}")
            rumps.quit_application()
            return

        # Start HTTP server in /tmp
        with open(HTTP_LOG, "w") as log:
            self.http = subprocess.Popen(
                [python, "-m", "http.server", str(HTTP_PORT)],
                cwd="/private/tmp", stdout=log, stderr=log
            )
        Path(HTTP_PID).write_text(str(self.http.pid))

        # Update status, copy URL, notify
        self._status.title = "● LiveRig Running"
        subprocess.run(["pbcopy"], input=self.url.encode(), check=False)
        rumps.notification(
            "LiveRig", f"Running · {self.host}",
            "iPad URL copied to clipboard", sound=False
        )

    # ── Menu callbacks ─────────────────────────────────────────────────────────
    def open_url(self, _):
        subprocess.run(["open", self.url], check=False)

    def copy_url(self, _):
        subprocess.run(["pbcopy"], input=self.url.encode(), check=False)
        rumps.notification("LiveRig", "Copied!", self.url, sound=False)

    def stop(self, _):
        for proc in [self.bridge, self.http]:
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
        for p in [PID_FILE, HTTP_PID]:
            Path(p).unlink(missing_ok=True)
        rumps.notification("LiveRig", "Stopped", "", sound=False)
        rumps.quit_application()


# ── Entry point ────────────────────────────────────────────────────────────────
def detect_host():
    r = subprocess.run(["scutil", "--get", "LocalHostName"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip() + ".local"
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == "__main__":
    support  = (sys.argv[1] if len(sys.argv) > 1
                else os.path.expanduser("~/Library/Application Support/LiveRig"))
    host     = sys.argv[2] if len(sys.argv) > 2 else detect_host()
    ipad_url = f"http://{host}:{HTTP_PORT}/liverig_controller_served.html"
    LiveRigMenu(support, host, ipad_url).run()
