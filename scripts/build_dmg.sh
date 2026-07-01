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
  echo "ERROR: $APP_PATH not found. Install/build LiveRig.app first." >&2
  exit 1
fi

echo "== Re-signing LiveRig.app (ad-hoc) =="
# Bundle contents (launcher script, Resources/LiveRig/) get edited directly
# during development -- that invalidates the existing code signature, which
# has previously caused stale-TCC-grant issues (see LIVERIG_MEMORY.md).
# Ad-hoc re-sign after every content change, including right before packaging.
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
1. Drag LiveRig.app into the Applications folder (shortcut provided here).
2. Launch LiveRig from Applications -- first run installs its own
   dependencies (Python venv, Homebrew if needed) and takes 3-5 minutes.
3. First run also deploys the Ableton Remote Script automatically to
   ~/Music/Ableton/User Library/Remote Scripts/LiveRig/. If you already
   had Ableton open, restart it (or toggle the Control Surface dropdown
   to None and back to LiveRig in Settings > Link, Tempo & MIDI) so it
   picks up the Remote Script.
4. See ONBOARDING.md in the LiveRig repo for full setup, including
   Ableton's one-time MIDI preferences step, which cannot be automated.
EOF

echo "== Building $DMG_NAME =="
rm -f "$DIST_DIR/$DMG_NAME"
hdiutil create -volname "$VOL_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DIST_DIR/$DMG_NAME"

rm -rf "$STAGING"
echo "== Done: $DIST_DIR/$DMG_NAME =="
