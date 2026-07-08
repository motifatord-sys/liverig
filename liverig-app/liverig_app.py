#!/usr/bin/env python3
"""LiveRig — unified macOS menu-bar app.

This is the single entry point for the whole "LiveRig.app" experience: it
bootstraps the MIDI-bridge environment, deploys the Ableton Remote Script,
serves the iPad-facing HTML, and runs the persistent menu-bar controller.

Why this file exists (2026-07-02): the previous architecture was a thin
bash launcher (Contents/MacOS/LiveRig) that, after some setup work, spawned
a raw `venv/bin/python liverig_menubar.py` process directly -- not through
macOS LaunchServices. That child process had no app-bundle identity of its
own, so macOS showed a generic "Python" rocket-ship icon and name in the
Dock, Cmd-Tab, and Force Quit, instead of LiveRig's own branding, for the
entire time LiveRig was running. Freezing this file into a real app via
py2app (see setup.py alongside this file) gives the actual running process
a proper CFBundleName/icon from launch to quit, closing that gap for good.

Two dependency tiers, kept deliberately separate:
  1. This app itself (rumps/PyObjC) -- frozen into the .app bundle by
     py2app at build time. End users never install anything for this part.
  2. The MIDI bridge subprocess (python-rtmidi + websockets) -- kept in a
     separate, lazily-created venv under Application Support, installed on
     first run via Homebrew if needed. Deliberately NOT frozen into the app
     bundle: python-rtmidi is a C-extension wrapping RtMidi, and installing
     it fresh per-machine is far more robust than trying to cross-bundle a
     compiled extension inside a py2app archive.

IMPORTANT: py2app itself only runs on macOS (needs Xcode Command Line
Tools + PyObjC) -- it cannot be built from a Linux sandbox. This file can be
read/edited anywhere, but the actual `python3 setup.py py2app` build step
(see scripts/build_app.sh) has to be run on a real Mac. Same constraint
this project already hit with codesign/hdiutil for the DMG.
"""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import rumps
from PyObjCTools import AppHelper

# ── Locate bundled resources -- works both frozen (inside the .app) and
# when run directly as a plain script during development. ───────────────────
if getattr(sys, "frozen", False):
    RESOURCES = Path(sys.executable).resolve().parent.parent / "Resources"
else:
    RESOURCES = Path(__file__).resolve().parent

SUPPORT            = Path.home() / "Library/Application Support/LiveRig"
BRIDGE_VENV         = SUPPORT / "venv"
BRIDGE_LOG          = Path("/private/tmp/liverig_bridge.log")
HTTP_LOG            = Path("/private/tmp/liverig_http.log")
PID_FILE            = Path("/private/tmp/liverig_bridge.pid")
HTTP_PID            = Path("/private/tmp/liverig_http.pid")
# Dedicated web root (2026-07-06): the http.server used to run with
# cwd=/private/tmp, which served EVERYTHING in /private/tmp -- bridge logs,
# other apps' temp files -- to the whole LAN. Now only this folder is exposed.
WWW_DIR             = Path("/private/tmp/liverig_www")
SERVED_HTML         = WWW_DIR / "liverig_controller_served.html"
HTTP_PORT           = 8080
WS_PORT             = 8765
REMOTE_SCRIPTS_DIR  = Path.home() / "Music/Ableton/User Library/Remote Scripts/LiveRig"

# rig_config.json handoff (ported 2026-07-02 from the retired
# LiveRig_Wired_Start.sh -- see _sync_rig_config() below for why).
# Portability (2026-07-06): the Desktop repo is a DEV convenience that only
# exists on David's machine. On any other Mac (DMG install), the canonical
# config lives in this app's own Application Support dir instead. All three
# components (this app, LiveRig.py, the bridge) search Desktop first, then
# Application Support -- so David's setup behaves exactly as before, and a
# repo-less machine still gets a real config instead of silent defaults.
REPO_RIG_CONFIG    = Path.home() / "Desktop/liverig/rig_config.json"
CANON_RIG_CONFIG   = SUPPORT / "rig_config.json"


def _active_rig_config():
    """The config file this machine actually uses: the dev repo's copy when
    the repo exists, otherwise the Application Support copy."""
    return REPO_RIG_CONFIG if REPO_RIG_CONFIG.parent.is_dir() else CANON_RIG_CONFIG
EXT_STORAGE_CONFIG = (Path.home() / "Library/Application Support/Ableton/Extensions"
                      / "LiveRig Setup Tool/storage/rig_config.json")
SERVED_RIG_CONFIG  = WWW_DIR / "rig_config.json"

# Shared secret for the bridge's WebSocket (2026-07-06). The WebSocket used
# to accept ANY client on the local network with zero auth -- fine at home,
# an open mixing desk on a venue's shared WiFi. The token is generated once,
# persisted here, read by the bridge at startup, and injected into the served
# HTML ({{BRIDGE_TOKEN}}) so only pages served by THIS app can connect.
TOKEN_FILE          = SUPPORT / "ws_token"


def _ensure_token():
    """Create (once) and return the shared WebSocket auth token."""
    try:
        if TOKEN_FILE.is_file():
            tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if tok:
                return tok
        SUPPORT.mkdir(parents=True, exist_ok=True)
        # os.urandom instead of the `secrets` module on purpose: this file is
        # frozen by py2app, which only bundles modules detected at build time.
        # A new stdlib import added after the last build would ImportError at
        # runtime; os is guaranteed present. 16 random bytes, hex-encoded.
        tok = "".join("%02x" % b for b in os.urandom(16))
        TOKEN_FILE.write_text(tok, encoding="utf-8")
        return tok
    except Exception as e:
        print(f"WARNING: ws token setup failed ({e}); bridge will run open.")
        return ""


def _run(cmd, **kw):
    # Default to a PYTHONHOME/PYTHONPATH-stripped environment (see
    # _clean_subprocess_env) for every subprocess this app spawns. This
    # matters most for the venv-creation and pip-install calls in
    # _ensure_bridge_venv(): those run a *different* Python (Homebrew's,
    # not this frozen app's), and without this, they silently inherited
    # this app's PYTHONHOME and built a venv that could never work --
    # explaining why even a from-scratch venv rebuild kept failing with
    # the same 'Failed to import encodings module' error.
    kw.setdefault("env", _clean_subprocess_env())
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _kill_port(port):
    r = _run(["lsof", "-ti", f"tcp:{port}"])
    for pid in r.stdout.strip().split():
        _run(["kill", pid])


def _detect_host():
    r = _run(["scutil", "--get", "LocalHostName"])
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


def _deploy_remote_script():
    """Port of the bash launcher's Remote Script sync (fixed 2026-07-01).
    Ableton loads LiveRig.py from its own Remote Scripts folder -- entirely
    separate from this bundle -- and nothing else keeps that copy current.
    Bundle Resources/LiveRig/ is the source of truth; unconditional
    overwrite, but only notify when the content actually changed, since a
    plain file copy does NOT make Ableton reload it (that still needs a
    restart or a Control Surface dropdown toggle -- nothing outside Live can
    force that part)."""
    src_dir = RESOURCES / "LiveRig"
    if not src_dir.is_dir():
        return
    REMOTE_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    changed = False
    for fname in ("LiveRig.py", "__init__.py"):
        src = src_dir / fname
        dest = REMOTE_SCRIPTS_DIR / fname
        if not src.exists():
            continue
        if not dest.exists() or src.read_bytes() != dest.read_bytes():
            changed = True
        dest.write_bytes(src.read_bytes())
    if changed:
        rumps.notification(
            "LiveRig — Remote Script Updated",
            "Restart Ableton Live to load it",
            "Or toggle the Control Surface dropdown to None and back to "
            "LiveRig in Settings > Link, Tempo & MIDI.",
        )


def _sync_rig_config():
    """Config handoff between the Setup Tool extension and the repo, plus
    keeping the iPad's served copy fresh. Two jobs, both ported 2026-07-02
    from LiveRig_Wired_Start.sh (a retired predecessor launcher) -- that
    script had this logic working correctly, but it was never carried
    forward into the bash launcher this app itself replaced, so it quietly
    stopped happening at some point. ONBOARDING.md kept describing this step
    as if it existed; it didn't, until now.

    1. Ableton Extensions can't write directly to the Desktop folder
       themselves (confirmed by the comment in the retired script -- an
       earlier attempt at a direct extension write caused repeated macOS
       Desktop-folder permission prompts). So the Setup Tool modal writes
       rig_config.json into its own sandboxed storage directory only, and
       THIS process -- which already holds the user's trust/permissions --
       does the copy into ~/Desktop/liverig/rig_config.json, but only when
       the extension's copy is actually newer (mtime compare).
    2. The controller page fetches "rig_config.json" as a plain relative GET
       against the http.server's document root (/private/tmp) -- so the
       repo's rig_config.json has to be copied there on every launch, or
       the iPad silently falls back to the hardcoded 4-keyboard/8-stem
       default with no error, regardless of what's actually configured.
    """
    target = _active_rig_config()

    if EXT_STORAGE_CONFIG.is_file():
        ext_mtime = EXT_STORAGE_CONFIG.stat().st_mtime
        tgt_mtime = target.stat().st_mtime if target.is_file() else 0
        if ext_mtime > tgt_mtime:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(EXT_STORAGE_CONFIG.read_bytes())
            rumps.notification(
                "LiveRig", "Config updated",
                "Synced a newer rig_config.json from the Setup Tool.",
                sound=False,
            )

    if target.is_file():
        WWW_DIR.mkdir(parents=True, exist_ok=True)
        SERVED_RIG_CONFIG.write_bytes(target.read_bytes())
    else:
        print(f"WARNING: rig_config.json not found at {target} -- "
              "controller will fall back to built-in defaults.")


def _clean_subprocess_env():
    """Environment for spawning the *separate* bridge-venv Python.

    This app itself is a frozen py2app bundle, and py2app's own bootstrap
    sets PYTHONHOME/PYTHONPATH (among others) in os.environ so its bundled
    interpreter can find its bundled stdlib inside the .app. subprocess.Popen
    inherits the parent's environment by default, so without this, the
    completely separate bridge venv's python inherits those same variables
    -- pointing it at the *frozen app's* Python resources instead of its own
    venv's stdlib. It then fails immediately with 'Failed to import
    encodings module', before running a single line of our code. This bit
    both the health check and the real subprocess launch identically, which
    is why simply rebuilding the venv didn't fix the previous crash: the
    venv itself was fine, the inherited environment was not."""
    env = os.environ.copy()
    for var in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(var, None)
    return env


def _bridge_venv_is_healthy():
    """Sanity-check that the venv's own Python can actually boot. A venv's
    interpreter is a symlink/shim pointing at the Homebrew Python that
    created it; if that Homebrew Python gets upgraded or removed later
    (e.g. `brew upgrade python`), the venv is left pointing at a dead
    interpreter that fails before running any of our code, with an error
    like 'Failed to import encodings module'. Path.exists() alone can't
    catch this -- the directory is still there, just non-functional."""
    python = BRIDGE_VENV / "bin/python"
    if not python.exists():
        return False
    try:
        result = subprocess.run([str(python), "-c", "import sys"],
                                 capture_output=True, timeout=10,
                                 env=_clean_subprocess_env())
        return result.returncode == 0
    except Exception:
        return False


def _ensure_bridge_venv():
    """One-time setup of the separate venv used only by the MIDI bridge
    subprocess. Returns False if the user cancelled a required install."""
    if BRIDGE_VENV.exists():
        if _bridge_venv_is_healthy():
            return True
        # Broken venv (e.g. left over from an upgraded/removed Homebrew
        # Python) -- wipe it so the fresh-install path below recreates it.
        print(f"WARNING: bridge venv at {BRIDGE_VENV} is broken, rebuilding it.")
        import shutil
        shutil.rmtree(BRIDGE_VENV, ignore_errors=True)

    rumps.notification("LiveRig", "Setting up for first time…",
                        "This takes a few minutes (once only).")
    brew = "/opt/homebrew/bin/brew"
    if not Path("/opt/homebrew/bin/python3").exists():
        if not Path(brew).exists():
            resp = rumps.alert(
                "LiveRig Setup",
                "LiveRig needs Homebrew + Python 3 for its MIDI bridge.\n\n"
                "This takes 3-5 minutes (once only). You may be asked for "
                "your Mac password.",
                ok="Continue", cancel="Cancel",
            )
            if resp != 1:
                return False
            _run(["/bin/bash", "-c",
                  "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"])
        _run([brew, "install", "python3"])

    _run(["/opt/homebrew/bin/python3", "-m", "venv", str(BRIDGE_VENV)])
    _run([str(BRIDGE_VENV / "bin/pip"), "install",
          "python-rtmidi", "websockets", "--quiet"])
    rumps.notification("LiveRig", "Setup complete!", "")
    return True


class LiveRigMenu(rumps.App):
    def __init__(self):
        super().__init__("LiveRig", title="🎹", quit_button=None)
        self.host = _detect_host()
        self.url = f"http://{self.host}:{HTTP_PORT}/liverig_controller_served.html"
        self.bridge = None
        self.http = None
        self._stopping = False
        self._restart_times = []   # watchdog: timestamps of recent restarts

        self._status = rumps.MenuItem("⏳ Starting…", callback=None)
        self.menu = [
            self._status,
            None,
            rumps.MenuItem("Open on iPad (Safari)", callback=self.open_url),
            rumps.MenuItem("Copy iPad URL", callback=self.copy_url),
            rumps.MenuItem("Resync Config from Setup Tool", callback=self.resync_config),
            rumps.MenuItem("Pre-Gig Check", callback=self.pre_gig_check),
            None,
            rumps.MenuItem("Stop LiveRig", callback=self.stop),
        ]

        threading.Thread(target=self._boot, daemon=True).start()

    # ── Boot sequence (runs in a background thread) ─────────────────────────
    def _boot(self):
        _deploy_remote_script()
        _sync_rig_config()
        if not _ensure_bridge_venv():
            rumps.quit_application()
            return

        for p in (PID_FILE, HTTP_PID):
            if p.exists():
                try:
                    os.kill(int(p.read_text().strip()), 15)
                    time.sleep(0.2)
                except Exception:
                    pass
                p.unlink(missing_ok=True)
        _kill_port(WS_PORT)
        _kill_port(HTTP_PORT)
        time.sleep(0.3)

        token = _ensure_token()

        html_src = RESOURCES / "live_rig_3_controller.html"
        # Explicit UTF-8: when launched via Finder/LaunchServices (no inherited
        # terminal locale), Python's default text encoding falls back to ASCII,
        # which crashes on this file's UTF-8 characters (e.g. dashes, icons).
        html = (html_src.read_text(encoding="utf-8")
                .replace("{{BRIDGE_HOST}}", self.host)
                .replace("{{BRIDGE_TOKEN}}", token))
        WWW_DIR.mkdir(parents=True, exist_ok=True)
        SERVED_HTML.write_text(html, encoding="utf-8")

        self._start_bridge()
        time.sleep(2)

        if self.bridge.poll() is not None:
            # rumps.alert() creates an NSAlert, and AppKit requires all
            # NSWindow/NSAlert creation to happen on the main thread.
            # _boot() runs in a background thread, so calling it directly
            # here crashes with NSInternalInconsistencyException -- which
            # was masking the actual "bridge failed to start" error.
            # AppHelper.callAfter hands the call to the main run loop.
            AppHelper.callAfter(
                rumps.alert, "LiveRig Error",
                f"Bridge failed to start.\nSee log: {BRIDGE_LOG}")
            rumps.quit_application()
            return

        self._start_http()

        self._status.title = "● LiveRig Running"
        subprocess.run(["pbcopy"], input=self.url.encode(), check=False)
        rumps.notification(
            "LiveRig", f"Running · {self.host}",
            "iPad URL copied to clipboard", sound=False,
        )

        threading.Thread(target=self._watchdog, daemon=True).start()

    # ── Subprocess launchers (shared by boot + watchdog restarts) ────────────
    def _start_bridge(self):
        bridge_python = str(BRIDGE_VENV / "bin/python")
        with open(BRIDGE_LOG, "a") as log:
            self.bridge = subprocess.Popen(
                [bridge_python, str(RESOURCES / "liverig_bridge_wired.py")],
                stdout=log, stderr=log, env=_clean_subprocess_env(),
            )
        PID_FILE.write_text(str(self.bridge.pid))

    def _start_http(self):
        bridge_python = str(BRIDGE_VENV / "bin/python")
        with open(HTTP_LOG, "a") as log:
            self.http = subprocess.Popen(
                [bridge_python, "-m", "http.server", str(HTTP_PORT)],
                cwd=str(WWW_DIR), stdout=log, stderr=log,
                env=_clean_subprocess_env(),
            )
        HTTP_PID.write_text(str(self.http.pid))

    # ── Watchdog (2026-07-06) ────────────────────────────────────────────────
    # Before this, the bridge/http subprocesses were checked exactly once,
    # 2s after launch, then never again -- a mid-show crash left the menu bar
    # saying "Running" while the iPad went dead. Now: poll every 5s, restart
    # whatever died, and rely on the iPad's existing auto-reconnect + the
    # bridge's connect-time full-state resync (0x4A) to bring everything back
    # without touching Ableton. Crash-loop guard: more than 4 restarts inside
    # 60s flips the menu to a visible failure state and pauses for a minute
    # instead of thrashing.
    def _watchdog(self):
        while not self._stopping:
            time.sleep(5)
            if self._stopping:
                return
            for name, proc, restart in (
                ("bridge", self.bridge, self._start_bridge),
                ("http server", self.http, self._start_http),
            ):
                if proc is None or proc.poll() is None:
                    continue
                now = time.time()
                self._restart_times = [t for t in self._restart_times
                                       if now - t < 60]
                if len(self._restart_times) >= 4:
                    self._status.title = "✕ LiveRig failing — see log"
                    rumps.notification(
                        "LiveRig", f"The {name} keeps crashing",
                        f"Pausing restarts for 60s. See {BRIDGE_LOG}",
                    )
                    time.sleep(60)
                    self._restart_times = []
                    continue
                self._restart_times.append(now)
                try:
                    restart()
                    self._status.title = "● LiveRig Running"
                    rumps.notification(
                        "LiveRig", f"Recovered: {name} restarted",
                        "The iPad will reconnect and resync automatically.",
                        sound=False,
                    )
                except Exception as e:
                    self._status.title = "✕ LiveRig error — see log"
                    rumps.notification("LiveRig",
                                       f"Failed to restart {name}", str(e))

    # ── Menu callbacks ───────────────────────────────────────────────────────
    def open_url(self, _):
        subprocess.run(["open", self.url], check=False)

    def copy_url(self, _):
        subprocess.run(["pbcopy"], input=self.url.encode(), check=False)
        rumps.notification("LiveRig", "Copied!", self.url, sound=False)

    def resync_config(self, _):
        # Manual trigger for _sync_rig_config() -- the only automatic trigger
        # is app launch, matching the retired LiveRig_Wired_Start.sh's
        # behavior. This lets a config saved via the Setup Tool modal take
        # effect with a page reload instead of a full LiveRig restart.
        _sync_rig_config()
        rumps.notification("LiveRig", "Config resynced",
                            "Reload the page on the iPad to pick it up.",
                            sound=False)

    def pre_gig_check(self, _):
        # Runs in a background thread (some checks take seconds); result is
        # shown via AppHelper.callAfter because NSAlert must be created on
        # the main thread (same constraint hit 2026-07-02, bug 2).
        threading.Thread(target=self._run_pre_gig_check, daemon=True).start()

    def _run_pre_gig_check(self):
        """One-click show-readiness check (2026-07-06). Every check that
        needs network or JSON goes through the bridge venv's python -- NOT
        this frozen process -- because py2app only bundles stdlib modules
        detected at build time (importing urllib/json here could
        ImportError at runtime until the next build_app.sh run)."""
        py = str(BRIDGE_VENV / "bin/python")
        token = _ensure_token()
        results = []

        class _Fail:
            returncode = 1
            stdout = stderr = ""

        def run_check(cmd, timeout):
            # A hung subprocess (e.g. dead HTTP server not refusing the
            # connection) must fail the check, not crash this thread.
            try:
                return _run(cmd, timeout=timeout)
            except Exception:
                return _Fail()

        def check(name, ok, hint=""):
            results.append(("✓" if ok else "✕") + " " + name +
                           ("" if ok or not hint else f" — {hint}"))
            return ok

        check("Bridge venv healthy", _bridge_venv_is_healthy(),
              "will self-rebuild on next launch (needs internet)")
        check("Bridge process running",
              self.bridge is not None and self.bridge.poll() is None,
              f"see {BRIDGE_LOG}")
        check("HTTP server running",
              self.http is not None and self.http.poll() is None,
              f"see {HTTP_LOG}")
        check("Auth token provisioned",
              TOKEN_FILE.is_file() and bool(TOKEN_FILE.read_text().strip()),
              "relaunch LiveRig to generate it")

        # Controller page served, with both placeholders actually injected.
        r = run_check([py, "-c", (
            "import urllib.request,sys;"
            f"b=urllib.request.urlopen('http://127.0.0.1:{HTTP_PORT}"
            "/liverig_controller_served.html',timeout=5).read().decode('utf-8');"
            "sys.exit(1 if ('{{BRIDGE_HOST}}' in b or '{{BRIDGE_TOKEN}}' in b)"
            " else 0)")], timeout=15)
        check("Controller page served + injected", r.returncode == 0,
              "relaunch LiveRig.app")

        # rig_config.json served and valid JSON.
        r = run_check([py, "-c", (
            "import urllib.request,json;"
            f"d=json.load(urllib.request.urlopen('http://127.0.0.1:{HTTP_PORT}"
            "/rig_config.json',timeout=5));"
            "print(len(d.get('keyboards',[])),len(d.get('stems',[])))")],
            timeout=15)
        check("rig_config.json served + valid"
              + (f" ({r.stdout.strip().replace(' ', ' KBD / ')} stems)"
                 if r.returncode == 0 else ""),
              r.returncode == 0, "use 'Resync Config from Setup Tool'")

        # WebSocket round-trip WITH auth: connect and receive the first
        # state push the bridge sends every new client.
        r = run_check([py, "-c", (
            "import asyncio,websockets\n"
            "async def m():\n"
            f"    async with websockets.connect('ws://127.0.0.1:{WS_PORT}"
            f"/?token={token}',open_timeout=5,close_timeout=2) as ws:\n"
            "        await asyncio.wait_for(ws.recv(), timeout=5)\n"
            "asyncio.run(m())")], timeout=20)
        check("WebSocket round-trip (with auth)", r.returncode == 0,
              f"see {BRIDGE_LOG}")

        # Remote Script deployed copy matches the bundle's copy.
        try:
            src = (RESOURCES / "LiveRig/LiveRig.py").read_bytes()
            dst = (REMOTE_SCRIPTS_DIR / "LiveRig.py").read_bytes()
            rs_ok = src == dst
        except Exception:
            rs_ok = False
        check("Remote Script synced to Ableton", rs_ok,
              "relaunch LiveRig.app, then restart Live")

        # Version strings consistent across the three bundled source files.
        def _ver(path, marker):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    # startswith, not `in`: comment lines and the
                    # FB_SCRIPT_VERSION definition also mention the marker.
                    if line.strip().startswith(marker) and "=" in line:
                        return line.split("=", 1)[1].strip().strip(";").strip("'\" ")
            except Exception:
                pass
            return "?"
        v_script = _ver(RESOURCES / "LiveRig/LiveRig.py", "LIVERIG_VERSION")
        v_bridge = _ver(RESOURCES / "liverig_bridge_wired.py", "LIVERIG_VERSION")
        v_html = _ver(RESOURCES / "live_rig_3_controller.html",
                      "const LIVERIG_VERSION")
        check(f"Versions match ({v_script})",
              v_script == v_bridge == v_html and v_script != "?",
              f"script={v_script} bridge={v_bridge} ui={v_html} — run scripts/deploy.sh")

        passed = sum(1 for r_ in results if r_.startswith("✓"))
        title = ("Pre-Gig Check — ALL CLEAR ✓" if passed == len(results)
                 else f"Pre-Gig Check — {len(results)-passed} PROBLEM(S)")
        body = "\n".join(results)
        if passed == len(results):
            body += ("\n\nReminders (can't be auto-checked): Ableton running "
                     "with the LiveRig Control Surface active, iPad on the "
                     "same WiFi, iPad page reloaded after any update (watch "
                     "the VER badge).")
        AppHelper.callAfter(rumps.alert, title, body)

    def stop(self, _):
        self._stopping = True   # keep the watchdog from resurrecting these
        for proc in (self.bridge, self.http):
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
        for p in (PID_FILE, HTTP_PID):
            p.unlink(missing_ok=True)
        rumps.notification("LiveRig", "Stopped", "", sound=False)
        rumps.quit_application()


if __name__ == "__main__":
    LiveRigMenu().run()
