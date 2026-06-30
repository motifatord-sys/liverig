# LiveRig Memory — Live, Writable State

> This file replaces `SESSION_BACKUP.md` (stale as of 2026-05-01) as the canonical project memory. It lives in the repo so it's read/write for Claude every session — no manual paste-in required. Updated on request ("Jesus Saves") or at natural session boundaries.

**Last updated:** 2026-06-30 (Looper feature fully working end-to-end: transport-stopped bug fixed, full 9-param Looper device map confirmed, Quantization dropdown + estimated progress bar built and deployed)

## Purpose & context

LiveRig is a custom iPad-based MIDI controller for Ableton Live, using Safari as the UI frontend, a Python WebSocket bridge, and a combination of Max for Live devices and a custom Python Remote Script as the backend. Goal: deeply integrated, bidirectional control surface beyond off-the-shelf solutions.

- **Environment:** Mac (`The-Beast-2147`), macOS 15, **Ableton Live 12.4.2** Suite + Max for Live (corrected — was misidentified as 12.3.8 earlier; 12.3.8 prefs folder is now stale/unused), Ableton Live 12 Beta + Extensions SDK installed
- **Live prefs/log path (current):** `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` — use this one going forward, not the 12.3.8 folder
- **Repo:** `https://github.com/motifatord-sys/liverig` (local: `~/Desktop/liverig/`)
- **GitHub auth:** Fine-grained PAT scoped to liverig repo (Contents read+write), via macOS Keychain / `osxkeychain`

## Current state — rig_config.json refactor: MERGED. Extensions SDK setup-tool: built, fixed, pipeline verified.

- **`refactor/rig-config` is merged to `main`** (merge commit `407d641`). This is the live state of the project, not a pending PR.
  - Controller HTML (`live_rig_3_controller.html`): confirmed via deliberate `maxPatches: 6` visible test, then reverted to 8.
  - Remote Script (`LiveRig.py`): confirmed via `Log.txt` line `rig_config loaded from /Users/dparks/Desktop/liverig/rig_config.json (4 keyboards)`.
  - **Remote Script v2** is the active architecture: each KBD page (config-driven count, was hardcoded 4) binds to a track's selected device, walks parameters in config-driven bank sizes (was hardcoded 8), attaches value+name listeners for bidirectional feedback on any plugin.
  - **Patches snapshot/rename** implemented: CAPTURE/RENAME buttons on Patches page; capture scope selectable per KBD page; snapshots store config-driven button/fader counts to localStorage as `patchSnapshots`; restore animates faders over 500ms ease-out-cubic, ~25 CC steps at 20ms intervals.
  - **Launcher fix:** `LiveRig_Wired_Start.sh` consolidated all Desktop-folder file I/O into a single Python heredoc, fixing repeated macOS Desktop-permission prompts.
  - **Known limitation, not yet fixed:** controller HTML still has 4 fixed page divs (`page-4`..`page-7`) and a 4-tab bar. `KBD_COUNT` can shrink below 4 cleanly but growing beyond 4 needs new markup — flagged for future work.

- **`feature/extensions-sdk-setup` — built by Claude Code, reconciled and bug-fixed by this chat, pipeline verified end-to-end. Not yet merged.**
  - New `liverig-setup-tool/` Ableton Extension: right-click any audio/MIDI track in Live Beta → "Configure LiveRig…" → modal form for rig name, KBD1-4 track bindings/bank size/buttons/faders/CC range, stems (label/track/default volume), max patches + animation ms.
  - Writes its working copy to `context.environment.storageDirectory/rig_config.json` (the SDK sandbox forbids writing directly to `~/Desktop/liverig/`).
  - `LiveRig_Wired_Start.sh` extended with a sync step: on every launch, compares mtimes of the extension's storage copy vs. `~/Desktop/liverig/rig_config.json` and `shutil.copy2`s the newer one over — this is the real (non-clipboard) handoff mechanism, decided 2026-06-26.
  - **Bug found & fixed (commit `b5fb8a2`):** the modal dialog's initial-data payload was spliced into `interface.html` as raw, un-encoded JSON (with literal quotes), causing a silent JS syntax error inside the sandboxed webview — dialog hung forever on "Loading…" with zero visible error anywhere. Fix: `encodeURIComponent()` the JSON payload before splicing it into the document, on top of the existing whole-document `encodeURIComponent()` for the `data:` URI (double-encoding pattern, standard for nesting URI-encoded content).
  - **Git history note:** Claude Code's first commit (`57826d2`) was built on a stale/diverged base; reconciled onto the correct tip as `a8dc1fe` (same file content, correct parent) before the fix (`b5fb8a2`) landed on top. Current branch tip: `b5fb8a2`.
  - **Verified working 2026-06-26:** saved a real config via the modal (KBD1-4 → MAIN KEYS/TOP KEYS/KEYS L/KEYS R, 8 stems DRUMS/PERC-LOOP/BASS/GTR/AUX/FX/VOCALS/LEAD VOCALS) → confirmed it landed byte-for-byte in `~/Desktop/liverig/rig_config.json` via the launcher's sync step (matching mtimes/size, content inspected directly).
  - **Outstanding before merge:** confirm `LiveRig.py` actually re-reads the synced config in a live Ableton session. As of last check, `Log.txt`'s last "rig_config loaded" line predates the new save — `LiveRig.py` only reads the config at Remote Script init, not live, so a Live restart (or Control Surface dropdown toggle to None and back) is required to pick it up. David is restarting Live now to retest; next step is re-checking `Log.txt` for a fresh "rig_config loaded… (4 keyboards)" line timestamped after the save, and confirming the iPad controller UI reflects the new labels/stems after a hard page reload.
  - **Hard constraint:** Ableton Live 12 Beta is currently the only Live install David can use for Extensions SDK work (just auto-updated to 12.4.5b5).

## On the horizon

- **Immediate next step:** verify `LiveRig.py` picks up the synced config after David's Live restart (check `Log.txt`), then verify the iPad controller UI reflects it.
- Once verified, open/merge the PR for `feature/extensions-sdk-setup` → `main` (merges second, after `refactor/rig-config`, per `BRANCHING_STRATEGY.md`).
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
- **2026-06-29 — "LiveRig won't open / keeps crashing" was not a crash.** Diagnosed live via Activity Monitor + checking all 3 monitors: the bridge process, http server, and the Tkinter status-window process were all alive and running — the window itself just never rendered in front of anything. A Python process launched in the background by a double-clicked AppleScript app doesn't get macOS "frontmost" status automatically, so the status window (and the clipboard'd iPad URL confirmation) silently opened behind every other app/Space. Fixed in `LiveRig_Wired_Start.sh`'s embedded `liverig_window.py` heredoc by forcing frontmost via `osascript`/System Events + `-topmost`/`lift()`/`focus_force()` right after `tk.Tk()` is created. This requires a one-time macOS Accessibility/Automation grant for Python → System Events (not a recurring prompt). Still unconfirmed/separate: David also reported recurring Desktop-folder permission prompts on every launch — no fresh evidence of that found in `liverig_launcher.log` during this diagnosis; needs its own follow-up if it recurs after this fix.
- **2026-06-29 — Recurring "LIVE RIG would like to access files in your Desktop folder" prompt: RESOLVED.** The app lives at `/Applications/LIVE RIG.app` (not `~/Desktop/liverig/`). Root cause was a broken/stale TCC grant for the app's identity (`com.apple.ScriptEditor.id.LIVE-RIG`), not multi-binary attribution. Fix (run once): `xattr -cr "/Applications/LIVE RIG.app"` (clear quarantine), `codesign --force --deep -s - "/Applications/LIVE RIG.app"` (stable ad-hoc signature), `tccutil reset SystemPolicyDesktopFolder` (wipe the stale grant so the next Allow sticks cleanly). Confirmed fixed: `ps aux` showed the app running directly from `/Applications/LIVE RIG.app/Contents/MacOS/applet` (not a translocated temp path), and a relaunch after granting Allow no longer re-prompts. If this regresses after future edits in Script Editor (re-saving an applet can reset its signature/quarantine state), re-run the same three commands.
- A `data:` URI's payload gets exactly one automatic `decodeURIComponent` pass by the browser. To safely splice JSON containing quotes into an HTML document that's itself being `encodeURIComponent`'d for a `data:` URI, double-encode: `encodeURIComponent` the JSON first, then let the whole-document encoding wrap around it. A single layer of encoding leaves literal quotes that break inline `<script>` string literals with a silent, invisible syntax error.
- Ableton Extensions cannot write to `~/Desktop` or other arbitrary user folders — only `context.environment.storageDirectory` and `tempDirectory`. Getting a config from an Extension onto the Desktop requires a separate trusted process (the launcher script) to do the copy.
- A Python Remote Script only reads its config file once, at control-surface init — not live. A new `rig_config.json` requires a Live restart (or toggling the Control Surface dropdown to None and back) before `LiveRig.py` will see it; check `Log.txt` for a fresh "rig_config loaded" timestamp to confirm.

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

## Looper feature — built 2026-06-29, fully working end-to-end as of 2026-06-30

- **Design locked in by David:** separate dedicated loop tracks (not KBD1-4); native Ableton Looper device control via the Live Object Model (not Cmd+M MIDI Map — the Looper device's single combined State enum doesn't map to discrete momentary CC buttons).
- **`rig_config.json`:** `loopers[]` array, 4 entries (`loop1`-`loop4`), bound to David's real dedicated loop tracks (confirmed working).
- **`LiveRig.py`:** inbound SysEx `SX_LOOP_REC/PLAY/STOP/UNDO` (0x4B-0x4E) + new `SX_LOOP_QUANT` (0x4F, value = `(loop_idx<<4)|quant_idx`); outbound `FB_LOOP_STATE` (0x48) + new `FB_LOOP_QUANT` (0x49, data = loop_idx, quant_idx). `_resolve_looper_track_index`/`_find_looper_device` resolve track+device by name/class_name. `_get_looper_state_map` reads the State param's `value_items` by substring match (Stop/Record/Play/Overdub — Overdub=3 not yet used). `_looper_set_state`/`_looper_undo` drive State/Undo directly.
  - **Critical fix (2026-06-29→30): the Looper's State param is a no-op via the Live API while the song transport is stopped** — confirmed via Cycling '74 forum research (explicitly requested by David). Writes are accepted silently but have zero effect on the device unless `song().is_playing` is already true. Fixed by calling `song().start_playing()` before every State write in `_looper_set_state`, mirroring what pressing the device's own on-screen button does. This was the root cause of "REC/PLAY does nothing" — confirmed fixed live by David.
  - **Full 9-parameter Looper device map confirmed via a one-shot diagnostic dump** (`_dump_looper_params`, still wired to fire once on connect for loop0 — harmless, not yet cleaned up): `Device On`, `State`, `Feedback`, `Reverse`, `Monitor`, `Speed`, `Quantization` (15 values: `Global, None, 8 Bars, 4 Bars, 2 Bars, 1 Bar, 1/2, 1/2T, 1/4, 1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32`), `Song Control`, `Tempo Control`. **Confirmed hard API ceiling: no loop-length/auto-stop control and no playhead/position readout exist anywhere in the Live API for this device** — matches independent forum research. Any "show real progress" feature is necessarily an estimate, not a true readout.
  - **New Quantization control** (`_get_looper_quant_param`, `_looper_set_quantization`, `_emit_looper_quant`/`_emit_all_looper_quants`, `_rebind_looper_quant_listeners`/`_unbind_looper_quant_listeners`) drives/reads the real device "Quantization" param — the same control as the dropdown in the Looper's own UI, repurposed as the bar-length/quantize selector David asked for. Wired into `_connect_listeners`, `disconnect`, `_on_tracks_changed`, `_emit_full_state`.
- **`liverig_bridge_wired.py`:** `loop_rec`/`loop_play`/`loop_stop`/`loop_undo` + new `loop_quant` JSON message types (carries `{index, value}`, packs into the `SX_LOOP_QUANT` value byte). `midi_in_callback` is a generic SysEx→WebSocket passthrough, so no bridge change was needed for the new `FB_LOOP_QUANT` feedback to reach the HTML.
- **`live_rig_3_controller.html`:** Looper row UI rebuilt — each of the 4 rows now has: name, a **Quantization `<select>` dropdown** (all 15 real device values, wired via `setLoopQuant`/`updateLooperQuant`, fb 0x49), an estimated progress bar, state label, REC/PLAY/STOP/UNDO buttons. `loopRecStart[]` anchors progress-phase calculation to the feedback-confirmed (not optimistic) rec-start moment, captured in `updateLooperState`. A 50ms `setInterval` (`startLoopProgressTimer`) computes `pct = (elapsed % durationSec) / durationSec * 100` from `tempo` + the selected Quantization's beat count (`LOOP_QUANT_BEATS`, only defined for the 4 whole-bar options — Global/None/sub-bar settings leave the bar static since duration can't be determined client-side). This is explicitly an estimate, agreed with David as an acceptable approximation given the API ceiling above.
- **Verified working live by David** (transport-fix confirmed: "ok it looks like its working"). Quantization dropdown + progress bar built and syntax-checked this session; **not yet confirmed live by David** — next step is reloading the Remote Script + refreshing the iPad page and testing.
- **Still pending cleanup:** remove the temporary `_dump_looper_params(0)` diagnostic call from `_connect_listeners` once no longer needed — currently harmless but not meant to be permanent.

## Pending tasks (carried forward, not yet superseded)

1. **Test the new Looper Quantization dropdown + estimated progress bar live** — reload the Remote Script, hard-refresh the iPad page, change Quantization on a loop and confirm the dropdown sticks both ways (UI→device and device→UI), and confirm the progress bar animates correctly during REC/PLAY for the 4 whole-bar settings.
2. **Remove the temporary `_dump_looper_params(0)` diagnostic call** from `_connect_listeners` in `LiveRig.py` now that the full parameter map is confirmed and documented above.
3. **Open/merge PR for `feature/extensions-sdk-setup` → `main`.**
4. Decide whether to delete superseded `SESSION_BACKUP.md` from repo root (archive copy already safe at `~/Documents/LiveRig_Archive/SESSION_BACKUP_2026-05-01.md`).
5. Restructure controller HTML markup to support >4 keyboards (currently capped by static page/tab divs).
6. Build "blue hand" mode — KBD pages auto-bind to currently-selected track's first 8 device params.
7. Build mixer listeners for mute/solo/volume on Master page.
8. Multi-computer routing UI (Option A architecture) — when needed.
9. **For Claude Code, Extensions SDK setup-tool (`liverig-setup-tool/`):** the modal currently only exposes KBD1-4 track bindings for editing. `rig_config.json`'s `stems[]` array drives a real "Stems" tab in the controller HTML with per-stem fader/mute/solo + live name/color feedback. The setup-tool's modal needs a matching "Stems" section so David can edit each `stems[].trackName` binding the same way he already edits KBD1-4 bindings — currently the only way to change a stem's bound track is hand-editing `rig_config.json` directly.

## How to resume in a new chat

1. Read this file first — it's the live state, not `SESSION_BACKUP.md`.
2. Continue from "Pending tasks" above — top item is confirming the Remote Script picked up the synced Extensions SDK config.
3. Respect channel isolation and architectural decisions listed above.
4. Don't reintroduce removed features (Record/Punch/Overdub on Setlist, etc.) without confirming with David first.
5. Use `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` for Ableton log checks — not the old 12.3.8 folder.
