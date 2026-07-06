#!/bin/bash
# LiveRig deploy — one command to sync all three deployment targets and verify.
#
# Why this exists (2026-07-06): LiveRig ships from ONE repo to THREE places,
# and stale copies at any of them have caused two multi-hour debugging
# sessions (see LIVERIG_MEMORY.md, "Remote Script deployment gap" and
# "Binding-status validation"):
#   1. /Applications/LiveRig.app/Contents/Resources/   (HTML, bridge, app, Remote Script)
#   2. ~/Music/Ableton/User Library/Remote Scripts/LiveRig/   (what Ableton loads)
#   3. the repo itself (source of truth, this folder)
#
# This script: (a) verifies the LIVERIG_VERSION string matches across the
# three source files, (b) copies repo -> bundle Resources -> Remote Scripts,
# (c) md5-verifies every copy, (d) reminds you what still needs a manual
# restart. Run it on the Mac after any change to HTML/bridge/app/Remote Script.
#
# NOTE: after changing liverig-app/liverig_app.py you should also eventually
# re-run scripts/build_app.sh + build_dmg.sh to keep dist/ current, but the
# bundle executes Resources/liverig_app.py as source (confirmed via
# __boot__.py 2026-07-06), so this deploy alone changes live behavior.

set -euo pipefail
cd "$(dirname "$0")/.."

REPO="$PWD"
BUNDLE="/Applications/LiveRig.app/Contents/Resources"
RS_DIR="$HOME/Music/Ableton/User Library/Remote Scripts/LiveRig"

# ── 1. Version consistency across the three source files ────────────────────
v_script=$(grep -m1 'LIVERIG_VERSION *= *"' LiveRig/LiveRig.py | sed 's/.*"\(.*\)".*/\1/')
v_bridge=$(grep -m1 'LIVERIG_VERSION *= *"' liverig_bridge_wired.py | sed 's/.*"\(.*\)".*/\1/')
v_html=$(grep -m1 "const LIVERIG_VERSION *= *'" live_rig_3_controller.html | sed "s/.*'\(.*\)'.*/\1/")

echo "Versions: script=$v_script bridge=$v_bridge html=$v_html"
if [ "$v_script" != "$v_bridge" ] || [ "$v_script" != "$v_html" ]; then
  echo "✕ LIVERIG_VERSION mismatch across source files — fix before deploying." >&2
  exit 1
fi

# ── 2. Copy repo → bundle Resources ─────────────────────────────────────────
if [ ! -d "$BUNDLE" ]; then
  echo "✕ $BUNDLE not found — is LiveRig.app installed?" >&2
  exit 1
fi
cp -f live_rig_3_controller.html        "$BUNDLE/"
cp -f liverig_bridge_wired.py           "$BUNDLE/"
cp -f liverig-app/liverig_app.py        "$BUNDLE/"
mkdir -p "$BUNDLE/LiveRig"
cp -f LiveRig/LiveRig.py LiveRig/__init__.py "$BUNDLE/LiveRig/"

# ── 3. Copy repo → Ableton Remote Scripts ───────────────────────────────────
mkdir -p "$RS_DIR"
cp -f LiveRig/LiveRig.py LiveRig/__init__.py "$RS_DIR/"

# ── 4. md5-verify every copy ────────────────────────────────────────────────
fail=0
check() {  # check <src> <dst>
  if [ "$(md5 -q "$1")" = "$(md5 -q "$2")" ]; then
    echo "  ✓ $2"
  else
    echo "  ✕ MISMATCH: $2" >&2; fail=1
  fi
}
echo "Verifying:"
check live_rig_3_controller.html "$BUNDLE/live_rig_3_controller.html"
check liverig_bridge_wired.py    "$BUNDLE/liverig_bridge_wired.py"
check liverig-app/liverig_app.py "$BUNDLE/liverig_app.py"
check LiveRig/LiveRig.py         "$BUNDLE/LiveRig/LiveRig.py"
check LiveRig/__init__.py        "$BUNDLE/LiveRig/__init__.py"
check LiveRig/LiveRig.py         "$RS_DIR/LiveRig.py"
check LiveRig/__init__.py        "$RS_DIR/__init__.py"
[ $fail -eq 0 ] || exit 1

echo ""
echo "Deployed LIVERIG_VERSION $v_script to all targets. Still manual:"
echo "  • HTML/bridge/app change → quit + relaunch LiveRig.app, hard-reload iPad"
echo "  • Remote Script change   → restart Ableton Live (or toggle the Control"
echo "    Surface dropdown to None and back), THEN reload the iPad"
echo "The iPad's red VER badge will confirm if anything is still stale."
