# LiveRig — iPad MIDI Controller for Ableton Live

Control Ableton Live from your iPad over your local WiFi network. Master/Stems/KBD volume faders, mute/solo, transport, native clip launching, Blue Hand mode (auto-follows the selected track), and Looper control — all bidirectional, so moves you make in Ableton show up on the iPad too.

For the full install-to-operation walkthrough, see **[ONBOARDING.md](ONBOARDING.md)**. For the technical history of how this project got here (and why things are built the way they are), see **[LIVERIG_MEMORY.md](LIVERIG_MEMORY.md)**.

---

## How it works

- **LiveRig.app** (built from `liverig-app/`, a py2app application) runs on your Mac. It's a menu-bar app that starts a WebSocket↔MIDI bridge and a small HTTP server, and deploys the Ableton Remote Script.
- **`LiveRig/LiveRig.py`** is the Ableton Remote Script — it reads `rig_config.json`, builds the MIDI map, and talks to LiveRig.app's bridge over a virtual MIDI port.
- **`live_rig_3_controller.html`** is the iPad-facing controller — open it in Safari (LiveRig.app's menu bar has a "Copy iPad URL" / "Open on iPad" shortcut).
- **`rig_config.json`** binds your actual Ableton track names to the keyboard/stem/looper faders, so the UI matches your real rig instead of a generic default.
- **`liverig-setup-tool/`** is an optional Ableton Extensions SDK tool — a right-click "Configure LiveRig…" modal for generating/editing `rig_config.json` without hand-editing JSON.

Everything runs over your local WiFi network — no USB, no internet required.

## Repo layout

| Path | What's in it |
|------|-------------|
| `ONBOARDING.md` | Full setup walkthrough, phase by phase, plus an honest list of what's not yet foolproof |
| `LIVERIG_MEMORY.md` | Running technical history — why things are built the way they are |
| `live_rig_3_controller.html` | The iPad controller page |
| `liverig_bridge_wired.py` | The MIDI↔WebSocket bridge, run as a subprocess by LiveRig.app |
| `rig_config.json` / `rig_config.example.json` / `rig_config.schema.json` | Your rig's track bindings, an example, and the JSON schema |
| `LiveRig/` | The Ableton Remote Script (`LiveRig.py`) |
| `liverig-app/` | The py2app project that builds LiveRig.app |
| `liverig-setup-tool/` | The Ableton Extensions SDK config-tool project |
| `scripts/` | `build_app.sh` (builds LiveRig.app) and `build_dmg.sh` (packages a distributable installer) — both must be run on macOS |
| `vendor/` | Vendored Extensions SDK/CLI packages |
| `docs/` | Secondary docs (branching strategy, Extensions SDK notes, macro tutorial, an older manual Remote Script install guide) |
| `archive/` | Retired/superseded files kept for history, not part of the current architecture (an old USB + Max for Live-based launcher and bridge scripts, old backup zips, an old manual Remote Script zip) |

## Quick start

See [ONBOARDING.md](ONBOARDING.md) for the complete walkthrough. In short:

1. `./scripts/build_app.sh` — builds and installs LiveRig.app (macOS only).
2. Launch LiveRig from Applications — first run installs the MIDI bridge's dependencies and deploys the Remote Script.
3. One-time in Ableton: Settings → Link, Tempo & MIDI → add a Control Surface row (Control Surface = `LiveRig`, Input/Output = `LiveRig Bridge`, Track + Remote on).
4. Open the iPad URL (from LiveRig's menu bar) in Safari.
