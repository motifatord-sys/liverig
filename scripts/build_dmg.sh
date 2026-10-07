#!/bin/bash
# Build a distributable LiveRig-Installer.dmg from /Applications/LiveRig.app.
#
# Run this ON YOUR MAC (not from a Claude session) whenever LiveRig.app's
# contents change -- hdiutil and codesign are macOS-only tools, so this
# can't be run from a sandboxed Claude session. Usage:
#
#   chmod +x scripts/build_dmg.sh
#   ./scripts/build_dmg.sh
#
# Produces ~/Desktop/liverig/dist/LiveRig-Installer.dmg
set -euo pipefail

APP_PATH="/Applications/LiveRig.app"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_DIR/dist"
DMG_NAME="LiveRig-Installer.dmg"
VOL_NAME="Install LiveRig"
STAGING="$(mktemp -d)"

if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: $APP_PATH not found. Run scripts/build_app.sh first to build/install it." >&2
  exit 1
fi

echo "== Re-signing LiveRig.app (ad-hoc) =="
# LiveRig.app is now a py2app-frozen bundle (built by scripts/build_app.sh,
# 2026-07-02 -- previously a hand-maintained bundle with a bash-script
# launcher). Rebuilding it, or editing Resources/LiveRig/ contents directly,
# invalidates any existing code signature, which has caused stale-TCC-grant
# issues before (see LIVERIG_MEMORY.md). Ad-hoc re-sign after every rebuild,
# including right before packaging.
xattr -cr "$APP_PATH"
codesign --force --deep -s - "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH" && echo "Signature OK"

echo "== Staging DMG contents =="
mkdir -p "$DIST_DIR"
cp -R "$APP_PATH" "$STAGING/LiveRig.app"
ln -s /Applications "$STAGING/Applications"

# Optional: drop a short readme onto the DMG for first-time installers.
cat > "$STAGING/Read Me.txt" <<'EOF'
LiveRig Installer
==================
Full step-by-step is in "LiveRig Quick Start.md" on this disk image. Short version:

1. Drag LiveRig.app into the Applications folder (shortcut provided here).
2. FIRST LAUNCH: because this is a test build, macOS blocks it once. In
   Applications, RIGHT-CLICK LiveRig -> Open -> Open. (If it says "damaged",
   run this in Terminal once, then right-click -> Open again:
      xattr -cr /Applications/LiveRig.app  )
   First launch takes 3-5 minutes and may ask for your Mac password -- it
   installs its own components and deploys the Ableton Remote Script.
3. In Ableton: Settings > Link, Tempo & MIDI > Control Surface = LiveRig,
   Input = LiveRig Bridge, Output = LiveRig Bridge (Track + Remote On for
   both). Restart Ableton once. (This MIDI step can't be automated.)
4. Open LiveRig-Template.als (on this disk image) -- its tracks are named to
   match LiveRig so everything binds automatically.
5. Click the menu-bar keyboard icon for the address; open it in a browser on
   the same WiFi (iPad ideal, or "Preview in Browser (this Mac)" to try it
   right here).

See "LiveRig Quick Start.md" for details and what to test.
EOF

# Friend-facing quick start + the demo template Live Set (if David built it).
QUICKSTART="$REPO_DIR/tester/TESTER_QUICKSTART.md"
TEMPLATE="$REPO_DIR/tester/LiveRig-Template.als"
[ -f "$QUICKSTART" ] && cp "$QUICKSTART" "$STAGING/LiveRig Quick Start.md"
if [ -f "$TEMPLATE" ]; then
  cp "$TEMPLATE" "$STAGING/LiveRig-Template.als"
else
  echo "NOTE: $TEMPLATE not found -- the DMG will ship WITHOUT the demo Live Set." >&2
  echo "      Build it once in Ableton per tester/TESTER_TEMPLATE.md, save it there, and re-run." >&2
fi

echo "== Building $DMG_NAME =="
rm -f "$DIST_DIR/$DMG_NAME"
hdiutil create -volname "$VOL_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DIST_DIR/$DMG_NAME"

rm -rf "$STAGING"
echo "== Done: $DIST_DIR/$DMG_NAME =="
