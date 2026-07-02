"""py2app build config for LiveRig.app.

Run on macOS only (see scripts/build_app.sh, which wraps the exact commands
below in a self-contained build-venv so it doesn't touch your regular Python
setup). Produces dist/LiveRig.app -- a real, properly-branded app bundle
whose running process shows up everywhere as "LiveRig" with LiveRig's own
icon, instead of the generic "Python" identity the old raw-subprocess
approach produced.

Data files are referenced from the repo root (one directory up) rather than
duplicated into liverig-app/, so there's exactly one source of truth for
live_rig_3_controller.html / liverig_bridge_wired.py / LiveRig/LiveRig.py --
the same class of stale-copy bug this project already hit once this session
(see LIVERIG_MEMORY.md, "Remote Script deployment gap") is not worth risking
a second time by duplicating these files here too.

Usage (normally via scripts/build_app.sh instead of directly):
    python3 -m venv build-venv
    build-venv/bin/pip install py2app rumps pyobjc
    build-venv/bin/python setup.py py2app
"""
from setuptools import setup

APP = ["liverig_app.py"]

DATA_FILES = [
    "../live_rig_3_controller.html",
    "../liverig_bridge_wired.py",
    ("LiveRig", ["../LiveRig/LiveRig.py", "../LiveRig/__init__.py"]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "LiveRig_icon.icns",
    "packages": ["rumps"],
    "plist": {
        "CFBundleName": "LiveRig",
        "CFBundleDisplayName": "LiveRig",
        "CFBundleExecutable": "LiveRig",
        "CFBundleIdentifier": "com.liverig.app",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1.0",
        "LSMinimumSystemVersion": "12.0",
        # False (Regular activation policy) on purpose: this app already
        # shows a persistent Dock icon today (that's the whole bug being
        # fixed -- it just shows Python's icon/name instead of LiveRig's).
        # This keeps the same Dock-visible behavior, correctly branded.
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    name="LiveRig",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
