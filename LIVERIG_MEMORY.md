# LiveRig Memory — Live, Writable State

> This file replaces `SESSION_BACKUP.md` (stale as of 2026-05-01) as the canonical project memory. It lives in the repo so it's read/write for Claude every session — no manual paste-in required. Updated on request ("Jesus Saves") or at natural session boundaries.

**Last updated:** 2026-06-26 (post-testing, pre-push)

## Purpose & context

LiveRig is a custom iPad-based MIDI controller for Ableton Live, using Safari as the UI frontend, a Python WebSocket bridge, and a combination of Max for Live devices and a custom Python Remote Script as the backend. Goal: deeply integrated, bidirectional control surface beyond off-the-shelf solutions.

- **Environment:** Mac (`The-Beast-2147`), macOS 15, **Ableton Live 12.4.2** Suite + Max for Live (corrected — was misidentified as 12.3.8 earlier; 12.3.8 prefs folder is now stale/unused), Ableton Live 12 Beta + Extensions SDK installed
- **Live prefs/log path (current):** `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` — use this one going forward, not the 12.3.8 folder
- **Repo:** `https://github.com/motifatord-sys/liverig` (local: `~/Desktop/liverig/`)
- **GitHub auth:** Fine-grained PAT scoped to liverig repo (Contents read+write), via macOS Keychain / `osxkeychain`

## Current state — rig_config.json refactor: TESTED & CONFIRMED, ready to push

- **Both halves of the scalability refactor are verified working in live Ableton sessions:**
  - Controller HTML (`live_rig_3_controller.html`): confirmed via deliberate `maxPatches: 6` visible test, then reverted to 8.
  - Remote Script (`LiveRig.py`): confirmed via `Log.txt` line `rig_config loaded from /Users/dparks/Desktop/liverig/rig_config.json (4 keyboards)`, logged repeatedly on 2026-06-26 (most recent 14:42:59).
- **David's explicit gate satisfied:** "test it in Live first, then push to github" — testing is done. Next action is commit + push to `refactor/rig-config`, pending David's go-ahead in chat.
- **Files ready to commit:** `rig_config.schema.json`, `rig_config.example.json`, `rig_config.json` (repo root + `LiveRig/` copy), updated `LiveRig.py`, updated `live_rig_3_controller.html`, updated `LiveRig_Wired_Start.sh`.
- **Remote Script v2** is the active architecture: each KBD page (now config-driven count, was hardcoded 4) binds to a track's selected device, walks parameters in config-driven bank sizes (was hardcoded 8), attaches value+name listeners for bidirectional feedback on any plugin.
- **Patches snapshot/rename** implemented: CAPTURE/RENAME buttons on Patches page; capture scope selectable per KBD page; snapshots store config-driven button/fader counts to localStorage as `patchSnapshots`; restore animates faders over 500ms ease-out-cubic, ~25 CC steps at 20ms intervals.
- **Launcher fix:** `LiveRig_Wired_Start.sh` consolidated all Desktop-folder file I/O (HTML hostname injection + rig_config.json copy to `/tmp`) into a single Python heredoc, fixing repeated macOS Desktop-permission prompts (was up to 4x per restart, now confirmed down to 1x by David).
- **Known limitation, not yet fixed:** controller HTML still has 4 fixed page divs (`page-4`..`page-7`) and a 4-tab bar. `KBD_COUNT` can shrink below 4 cleanly but growing beyond 4 needs new markup — flagged for future work.
- **Extensions SDK** installed, under evaluation for a parallel workstream — no work started yet this cycle.

## On the horizon

- **Immediate next step:** commit + push `refactor/rig-config` branch once David gives the go-ahead (asked, awaiting reply as of last message).
- **Extensions SDK branch** (`feature/extensions-sdk-setup`, Claude Code): build a rig-setup/configuration tool against Ableton's Extensions SDK, writing configs conforming to the same schema. Not started.
- **>4 keyboard support:** requires restructuring static page/tab markup in `live_rig_3_controller.html` — deferred, no timeline.
- See `BRANCHING_STRATEGY.md` for fork points, merge order, and conflict zones.

## Key learnings & principles

- `Song.last_event_time` is **not listenable** in Live 12.3.8 — crashes on subscription. Read on demand only.
- `current_song_time` fires per audio block — **never subscribe directly**; poll via `schedule_message` at 10 Hz instead.
- Every listener subscription needs defensive `try/except` to avoid "Observer already connected" RuntimeErrors.
- Live's Cmd+M MIDI mapping table is **not API-accessible** — `get_midi_mappings_serialized`, `midi_mappings`, `set_or_delete_midi_mapping` confirmed missing.
- True bidirectional plugin parameter feedback comes from **DeviceComponent-style parameter value listeners**, not Cmd+M.
- TouchOSC's apparent bidirectionality requires ClyphX Pro (a Remote Script) running in the background — not native.
- Live's Remote Script slot limit is 6; LiveRig consumes 1.
- Live 12.x Remote Scripts run on Python 3.11.
- Editing a Remote Script requires either a Live restart or toggling the Control Surface dropdown to None and back (forces re-import).
- Filename mangling: messaging clients auto-convert `Start.sh`-style names into markdown links — rename via Finder to work around it.
- **Ableton creates a new `Live <version>` prefs folder on every update**, each with its own `Log.txt`. Always confirm current Live version before trusting a log file's mtime — an old folder will sit untouched and silently look "stale" even after real restarts. Current: 12.4.2.
- macOS Desktop-folder permission prompts are granted per-binary, not per-app — multiple tools (sed, cp, python3) touching the same protected folder each trigger separate prompts. Fix: route all file I/O through one trusted interpreter.

## Approach & patterns

- Iterative debug-and-commit workflow, changes pushed to GitHub in logical batches.
- Parallel workstream strategy: Claude Code owns the Extensions SDK branch, this chat owns the scalability refactor — kept separate, coordinated via `BRANCHING_STRATEGY.md`.
- Research-driven decisions: analyzed Komplete Kontrol S88 MK3 Remote Script (.pyc bytecode) to confirm architectural patterns before building.
- Features lost to session compaction get reconstructed from scratch — hence this file living in the repo instead of only in chat memory.

## Architectural decisions carried forward (from earlier sessions)

1. Hybrid M4L + Remote Script: Remote Script handles listeners/transport/selected-track awareness; M4L stays for per-track utilities. Both can run simultaneously.
2. Scene firing as song-state mechanism — no hardcoded song-to-chain mappings; use Ableton scenes with dummy clips automating Chain Selectors/Macros.
3. Channel isolation: CH16 transport only, KBD1-4 on CH1-4, Click/Guide/Loops/Stems CH5, Pads CH10, Pads FX CH1.
4. Locator naming convention: `Song: <name>` prefix = song boundary; other names = sections.
5. Multi-computer support deferred (Option A reserved): per-section bridge routing on iPad, for future use.
6. Omnisphere setup: each KBD track holds an Instrument Rack with 3 Omnisphere chains via Chain Selector, each in Live Mode with 8 patches → 24 sounds × 4 keyboards = 96 sound slots.

## Tools & resources

- Ableton Live 12.3.8 Suite + Max for Live (primary DAW)
- Ableton Live 12 Beta + Extensions SDK (parallel exploration)
- Python (WebSocket bridge, Remote Script)
- Tkinter (launcher window UI)
- Safari on iPad (controller UI frontend)
- GitHub (`motifatord-sys/liverig`)
- Claude Code (Extensions SDK branch work)

## Pending tasks (carried forward, not yet superseded)

1. **Commit + push `refactor/rig-config` to GitHub** — testing complete, awaiting David's go-ahead in chat (next action).
2. Cut `feature/extensions-sdk-setup` branch (Claude Code) — not started.
3. Decide whether to delete superseded `SESSION_BACKUP.md` from repo root (archive copy already safe at `~/Documents/LiveRig_Archive/SESSION_BACKUP_2026-05-01.md`).
4. Restructure controller HTML markup to support >4 keyboards (currently capped by static page/tab divs).
5. Build "blue hand" mode — KBD pages auto-bind to currently-selected track's first 8 device params.
6. Build mixer listeners for mute/solo/volume on Master page.
7. Multi-computer routing UI (Option A architecture) — when needed.

## How to resume in a new chat

1. Read this file first — it's the live state, not `SESSION_BACKUP.md`.
2. Continue from "Pending tasks" above — top item is the GitHub push, gated on David's confirmation.
3. Respect channel isolation and architectural decisions listed above.
4. Don't reintroduce removed features (Record/Punch/Overdub on Setlist, etc.) without confirming with David first.
5. Use `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` for Ableton log checks — not the old 12.3.8 folder.
