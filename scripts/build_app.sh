#!/bin/bash
# Build LiveRig.app from the liverig-app/ py2app project.
#
# Run this ON YOUR MAC (not from a Claude session) -- py2app needs macOS +
# Xcode Command Line Tools + PyObjC, none of which are available in a
# sandboxed Claude session (same constraint this project already hit with
# codesign/hdiutil for the DMG). Usage:
#
#   chmod +x scripts/build_app.sh
#   ./scripts/build_app.sh
#
# Produces liverig-app/dist/LiveRig.app and installs it to /Applications,
# replacing whatever's there. Quit LiveRig from the menu bar first if it's
# currently running.
#
# Run scripts/build_dmg.sh afterward if you want a distributable installer.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$REPO_DIR/liverig-app"
BUILD_VENV="$APP_DIR/build-venv"

cd "$APP_DIR"

echo "== Setting up an isolated build environment =="
# A separate venv just for the py2app BUILD toolchain (py2app + rumps,
# which pulls in PyObjC) -- deliberately NOT the same venv LiveRig creates
# at runtime for its MIDI bridge (python-rtmidi/websockets, installed via
# Homebrew's python3 the first time the app launches). Building an app and
# running one have different dependencies; keeping the two apart means
# rebuilding this never touches an end user's runtime venv, and vice versa.
if [ ! -d "$BUILD_VENV" ]; then
  python3 -m venv "$BUILD_VENV"
fi
"$BUILD_VENV/bin/pip" install --upgrade pip --quiet
"$BUILD_VENV/bin/pip" install py2app rumps --quiet

echo "== Cleaning previous build =="
rm -rf build dist

echo "== Building LiveRig.app =="
"$BUILD_VENV/bin/python" setup.py py2app

if [ ! -d "dist/LiveRig.app" ]; then
  echo "ERROR: py2app did not produce dist/LiveRig.app -- check the output above." >&2
  exit 1
fi

echo "== Installing to /Applications =="
if pgrep -f "LiveRig.app/Contents/MacOS/LiveRig" >/dev/null 2>&1; then
  echo "LiveRig is currently running -- quit it from the menu bar first, then re-run this script." >&2
  exit 1
fi
rm -rf /Applications/LiveRig.app
cp -R dist/LiveRig.app /Applications/LiveRig.app

echo "== Done: /Applications/LiveRig.app built and installed =="
echo "Launch it and check the Dock -- it should now show LiveRig's own icon and name, not Python's."
echo "Next: ./scripts/build_dmg.sh if you want a distributable installer."
