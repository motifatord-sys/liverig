# LiveRig Session Backup — Last updated 2026-05-01

## Project Overview

**LiveRig** is a custom iPad-based MIDI controller for Ableton Live, built by David (motifatord-sys on GitHub) on a Mac (`The-Beast-2147`, macOS 15, **Live 12.3.8** Suite + Max for Live).

**Repo:** https://github.com/motifatord-sys/liverig
**Local repo:** `~/Desktop/liverig/` on user's Mac
**Username:** `dparks`

## Architecture (current)

```
iPad Safari (live_rig_3_controller.html)
    ↓ WebSocket :8765
Python Bridge (liverig_bridge_wired.py)
    ↓ Virtual MIDI: "LiveRig Bridge"
Ableton Live
    ├── M4L Device (LiveRig_Bridge.maxpat + liverig_send.js + liverig_dispatch.js)
    │   └── Polling-based state, file-based JSON sharing, SysEx dispatch (LEGACY — optional)
    └── LiveRig Remote Script (~/Music/Ableton/User Library/Remote Scripts/LiveRig/)
        ├── __init__.py — entry point
        └── LiveRig.py — main class, listener-based feedback
```

Both M4L and Remote Script paths can coexist. **Remote Script is the recommended path going forward** — listener-based, no polling, no audio thread cost.

## Latest GitHub Commit
**`dbcdb3d`** — "K4 magenta, Latch buttons, Setlist marker nav, scene firing, larger statusbar, minimizable launcher"

Pending uncommitted changes:
- Remote Script (`LiveRig/__init__.py` and `LiveRig.py`)
- Updated `live_rig_3_controller.html` with `onRemoteScriptFeedback` parser
- `REMOTE_SCRIPT_INSTALL.md` documentation

## Key Files

### In repo (`~/Desktop/liverig/`)
- `live_rig_3_controller.html` — iPad UI with Remote Script feedback parser
- `liverig_bridge_wired.py` — Python WebSocket + UDP + HTTP + file watcher (handles transport_* and scene_fire SysEx emit)
- `liverig_send.js` v13 — M4L Max JS for state polling
- `liverig_dispatch.js` — M4L SysEx → Live API dispatcher
- `LiveRig_Bridge.maxpat` v13 — M4L device patch
- `LiveRig_Wired_Start.sh` — Launcher with minimizable Tkinter window
- `MACRO_TUTORIAL.md` — Instrument Rack + Macro setup guide
- `REMOTE_SCRIPT_INSTALL.md` — Remote Script install/usage guide
- `README.md`

### Installed at `~/Music/Ableton/User Library/Remote Scripts/LiveRig/`
- `__init__.py` — entry point
- `LiveRig.py` — main control surface class

### Status: Remote Script is loaded and working
- Live 12.3.8 logs `LiveRig Remote Script loaded.` on startup
- Configured at MIDI Remote Script slot 6 with Input/Output = `LiveRig Bridge`
- Defensive try/except wrapping prevents "Observer already connected" errors from killing init

## Major Features Working

### iPad UI (Tab order)
1. **Master** — 8 channel strips with Mute/Solo (86px tall)
2. **Setlist** — 2-column library/active list with autoplay, marker nav
3. **Transport** — full transport with native SysEx
4. **Patches** — single-active radio, tap-and-hold rename
5. **Kbd1-4** — 8 faders + 8 buttons + 8 Latch buttons. K1=purple, K2=teal, K3=orange, K4=magenta
6. **Looper** — Rec/Play/Stop on CH16
7. **Pads** — 16 pads on CH10, fire-on-press
8. **Clips** — 8x8 clip grid + scene-launch column with scene names

### Status Bar (44px tall)
- Connection dot (green when connected)
- Bridge label
- Beat pulse dot
- Large BPM display
- Meta info, IP, PANIC buttons

### Tab Reordering
Long-press tab 600ms → wiggle/edit mode → drag → tap any tab to exit. Order persisted.

## MIDI Map (channel-isolated)

| Section | Channel | Notes/CCs |
|---------|---------|-----------|
| Keyboards 1-4 buttons (B1-B8) | CH1-4 | CC20-27 |
| Keyboards 1-4 Latch (B9-B16, golden) | CH1-4 | CC28-35 |
| Keyboards 1-4 faders | CH1-4 | CC10-17 |
| Master vol K1-K4 | CH1-4 | CC7 |
| Master mute/solo | CH1-4 | CC1, CC2 |
| Click/Guide/Loops/Stems | CH5 | CC20-23 vol, CC24-27 mute, CC28-31 solo |
| Pads | CH10 | Notes 36-51 |
| Pads FX | CH1 | CC70-73 |
| Patches PC | CH1-4 | PC0-7 |
| Transport | CH16 | CC116/117/118/119/112/113/114/115/111 |
| Tap Tempo | CH16 | CC89 |
| Tempo bend, BPM, nudge | CH16 | CC107/108/14/91/90 |
| Marker prev/next | CH16 | CC92/93 |
| Looper | CH16 | CC80-87 |
| Clip launcher | CH16 | Notes 48-111 + CC52-68 |

## Native Transport via SysEx (no Cmd+M needed)

Format: `F0 7D <code> <value> F7`. Both M4L AND Remote Script handle these:

| Code | Action | Live API |
|------|--------|----------|
| 0x30 | Locator jump | `cue_points[N].jump()` |
| 0x31 | Next marker | `song.jump_to_next_cue()` |
| 0x32 | Prev marker | `song.jump_to_prev_cue()` |
| 0x33 | Scene fire | `scenes[N].fire()` |
| 0x40 | Play | `song.start_playing()` |
| 0x41 | Stop | `song.stop_playing()` |
| 0x42 | Record toggle | `song.record_mode = !rec` |
| 0x43 | Overdub toggle | `song.overdub = !od` |
| 0x44 | Metronome toggle | `song.metronome = !m` |
| 0x45 | Loop toggle | `song.loop = !l` |
| 0x46 | Punch in toggle | `song.punch_in = !pi` |
| 0x47 | Tap tempo | `song.tap_tempo()` |
| 0x48 | Undo | `song.undo()` if can_undo |
| 0x49 | Redo | `song.redo()` if can_redo |
| 0x4A | Request full state (Remote Script only) | re-emit everything |

## Remote Script Feedback SysEx (script → bridge → iPad)

Format: `F0 7D 60 <fb_type> <data...> F7`

| fb_type | Meaning | Data |
|---------|---------|------|
| 0x00 | Transport state | byte: 0=stop, 1=play, 2=record |
| 0x01 | BPM | uint14 (BPM × 100) |
| 0x02 | Song time (ms) | uint28 |
| 0x03 | Song length (ms) | uint28 |
| 0x10 | Cue update | idx, time(uint28), len, name |
| 0x12 | Cue list begin | count |
| 0x13 | Cue list end | (none) |
| 0x20 | Scene update | idx, len, name |
| 0x22 | Scene list begin | count |
| 0x23 | Scene list end | (none) |
| 0x30 | Selected track | idx, len, name |
| 0x40 | Macro value | trackIdx, macroIdx, value14, len, name |

## Remote Script Implementation Notes (lessons learned)

1. **`Song.last_event_time` is NOT a listenable property** — only readable. Don't subscribe to it; read on demand.
2. **`current_song_time` listener fires per audio block (~hundreds of Hz)** — DO NOT subscribe. We poll-emit at 10 Hz via `schedule_message(1, ...)` which equals 100ms.
3. **"Observer already connected" RuntimeError** can happen if a previous load attempt partially registered listeners that didn't clean up. Solution: wrap each listener subscription in try/except so one failure doesn't kill init.
4. **Live's Remote Script slot limit is 6.** LiveRig consumes 1 slot when active.
5. **Live 12.x uses Python 3.11** for Remote Scripts.
6. **Editing Remote Script requires either Live restart OR toggle Control Surface dropdown to None and back to LiveRig** (forces re-import).
7. **Both `Network (LiveRig)` and `LiveRig Bridge` MIDI ports must have Track/Sync/Remote checked** in Settings → MIDI for inbound SysEx and outbound feedback to flow.

## Architectural Decisions Made

1. **Hybrid M4L + Remote Script.** Remote Script handles listeners, transport, selected-track awareness. M4L stays for per-track utilities. Both can run simultaneously.
2. **Scene firing as song-state mechanism.** Don't hardcode song-to-chain mappings in LiveRig. Use Ableton scenes with dummy clips that automate Chain Selectors, Macros, etc.
3. **Channel isolation:** CH16 transport only. KBD on CH1-4. Click/Guide/Loops/Stems CH5. Pads CH10. Pads FX CH1.
4. **Locator naming convention:** `Song: <name>` prefix → song boundary. Other names → sections.
5. **Multi-computer support deferred (Option A reserved):** Per-section bridge routing on iPad for future use.
6. **Omnisphere setup:** Each KBD track holds Instrument Rack with 3 Omnisphere chains via Chain Selector, each Omnisphere in Live Mode with 8 patches. 24 sounds × 4 keyboards = 96 sound slots.

## Pending Tasks

1. ⏳ **Push Remote Script + updated HTML to GitHub** (next step)
2. ⏳ **Test Remote Script feedback in real session** — confirm BPM updates instantly, macro feedback works
3. ⏳ **Complete Macro tutorial setup** in test template (wrap Omnisphere in Instrument Rack, map params, Cmd+M map LiveRig faders)
4. ⏳ **MIDI-map clip stop buttons** in Ableton via Cmd+M (CC52-59 + CC68 on CH16)
5. ⏳ **Build CC-feedback mapping** path using `map_midi_cc_with_feedback_map` — Cmd+M map iPad faders to ANY parameter with auto feedback
6. ⏳ **Build "blue hand" mode** — KBD pages auto-bind to currently-selected track's first 8 device params
7. ⏳ **Build mixer listeners** for mute/solo/volume on Master page
8. ⏳ **Multi-computer routing UI** when needed (Option A architecture)

## Important Environmental Notes

- **Filename mangling:** User's iPad/messaging client auto-rewrites filenames matching markdown link patterns (`Start.sh` becomes `[Start.sh](http://Start.sh)` when pasted from chat to terminal). Worked around — files renamed via Finder.
- **tkinter required for minimizable launcher window:** `python-tk` installed via Homebrew. Launcher detects tkinter at runtime and falls back to legacy modal `osascript` dialog if missing.
- **Live's Remote Script slot limit is 6.** LiveRig consumes 1 slot.
- **Live 12.3.8** is current installed version.

## Recent Session Pivots (2026-05-01)

1. Built Remote Script for true bidirectional Macro feedback (event-driven vs M4L polling)
2. Fixed `last_event_time` listener bug (property isn't listenable)
3. Replaced per-block `current_song_time` listener with 10 Hz polling tick to avoid audio stutter
4. Added defensive try/except wrapping for "Observer already connected" RuntimeError
5. Confirmed Remote Script loads and works in Live 12.3.8

## .als File Analysis (deferred)

User uploaded `LEONARD_RAY_-_SECRET_SAUCE_-_TEMPLATE_-_AUX.als` mid-session. Findings preserved:
- 57 MIDI / 12 audio / 16 group / 1 return tracks
- 13 Instrument Racks total — 4 named "midi keys 1-4" are LiveRig KBD candidates
- 0 cue points
- 133 existing MIDI mappings, heavy on CH1 and CH16
- Channel conflict warning: template uses CH1 heavily — would clash with LiveRig KBD1's CC10-17 and CC20-35
- Recommendation: move LiveRig keyboard CCs to CH9-12 if integrating with this template

## Output Files Available

All in `/mnt/user-data/outputs/`:
- `live_rig_3_controller.html`
- `liverig_bridge_wired.py`
- `liverig_send.js`
- `liverig_dispatch.js`
- `LiveRig_Bridge.maxpat`
- `LiveRig_Wired_Start.sh`
- `MACRO_TUTORIAL.md`
- `REMOTE_SCRIPT_INSTALL.md`
- `LiveRig_RemoteScript.zip` (the Remote Script folder)
- `SESSION_BACKUP.md` (this file)

## How to Resume in a New Chat

If conversation is compacted, paste this backup at the top of the new chat. The new Claude instance should:

1. Acknowledge the backup
2. Continue from "Pending Tasks" — likely starting with GitHub push for Remote Script
3. Maintain architectural decisions
4. NOT reintroduce removed features (Record/Punch/Overdub on Setlist, etc.)
5. Respect channel isolation
6. Use Tab order: Master · Setlist · Transport · Patches · Kbd1-4 · Looper · Pads · Clips
7. Preserve Remote Script lessons learned (no `last_event_time` listener, no `current_song_time` listener, defensive try/except wrapping)
