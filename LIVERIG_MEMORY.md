# LiveRig Memory — Live, Writable State

> This file replaces `SESSION_BACKUP.md` (stale as of 2026-05-01) as the canonical project memory. It lives in the repo so it's read/write for Claude every session — no manual paste-in required. Updated on request ("Jesus Saves") or at natural session boundaries.

**Last updated:** 2026-06-30 (>4 keyboard support shipped — dynamic MIDI channel assignment + tab/page generation, commit `4e971c3`; dead `_dump_looper_params` method deleted, commit `4e971c3`; FX Return faders on Master page, automatic mute/solo via Remote Script, JS TDZ crash fix from earlier the same day)

## App bundle architecture — CRITICAL deployment fact

- `/Applications/LiveRig.app/Contents/MacOS/LiveRig` is a **shell launcher script**, NOT a binary.
- On **every launch**, it runs `cp -f "$RESOURCES/live_rig_3_controller.html" "$SUPPORT/"` and similarly for `liverig_bridge_wired.py` and `liverig_menubar.py`.
- **Bundle Resources (`/Applications/LiveRig.app/Contents/Resources/`) is the true source of truth** — `Application Support/LiveRig/` always gets overwritten.
- To deploy HTML/Python changes: update `~/Desktop/liverig/` source files, copy to bundle Resources (use a Python script — cp and rsync silently appear to succeed but the launcher's cp overwrites on next launch), then restart the app.
- `liverig_menubar.py` reads `live_rig_3_controller.html` from Application Support, injects `{{BRIDGE_HOST}}` → writes to `/private/tmp/liverig_controller_served.html` — this is what the HTTP server (port 8080) actually serves.
- **Always use `/private/tmp/` not `/tmp/`** — macOS symlinks `/tmp` → `/private/tmp` but `sed >` file writes through `/tmp` can silently fail. All paths in `liverig_menubar.py` use `/private/tmp/` (fixed commit `44f365d`).

## Purpose & context

LiveRig is a custom iPad-based MIDI controller for Ableton Live, using Safari as the UI frontend, a Python WebSocket bridge, and a combination of Max for Live devices and a custom Python Remote Script as the backend. Goal: deeply integrated, bidirectional control surface beyond off-the-shelf solutions.

- **Environment:** Mac (`The-Beast-2147`), macOS 15, **Ableton Live 12.4.2** Suite + Max for Live (corrected — was misidentified as 12.3.8 earlier; 12.3.8 prefs folder is now stale/unused), Ableton Live 12 Beta + Extensions SDK installed
- **Live prefs/log path (current):** `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` — use this one going forward, not the 12.3.8 folder
- **Repo:** `https://github.com/motifatord-sys/liverig` (local: `~/Desktop/liverig/`)
- **GitHub auth:** Fine-grained PAT scoped to liverig repo (Contents read+write), via macOS Keychain / `osxkeychain`

## Current state — rig_config.json refactor: MERGED. Extensions SDK setup-tool: MERGED.

- **`refactor/rig-config` is merged to `main`** (merge commit `407d641`). This is the live state of the project, not a pending PR.
  - Controller HTML (`live_rig_3_controller.html`): confirmed via deliberate `maxPatches: 6` visible test, then reverted to 8.
  - Remote Script (`LiveRig.py`): confirmed via `Log.txt` line `rig_config loaded from /Users/dparks/Desktop/liverig/rig_config.json (4 keyboards)`.
  - **Remote Script v2** is the active architecture: each KBD page (config-driven count, was hardcoded 4) binds to a track's selected device, walks parameters in config-driven bank sizes (was hardcoded 8), attaches value+name listeners for bidirectional feedback on any plugin.
  - **Patches snapshot/rename** implemented: CAPTURE/RENAME buttons on Patches page; capture scope selectable per KBD page; snapshots store config-driven button/fader counts to localStorage as `patchSnapshots`; restore animates faders over 500ms ease-out-cubic, ~25 CC steps at 20ms intervals.
  - **Launcher fix:** `LiveRig_Wired_Start.sh` consolidated all Desktop-folder file I/O into a single Python heredoc, fixing repeated macOS Desktop-permission prompts.
  - **Known limitation, not yet fixed:** controller HTML still has 4 fixed page divs (`page-4`..`page-7`) and a 4-tab bar. `KBD_COUNT` can shrink below 4 cleanly but growing beyond 4 needs new markup — flagged for future work.

- **`feature/extensions-sdk-setup` — built by Claude Code, reconciled and bug-fixed by this chat, pipeline verified end-to-end. MERGED to `main` as squash commit `c4c9430` ("Extensions SDK setup tool + Looper Quantization + menu bar launcher (#2)") — confirmed 2026-06-30 via `git log`, no divergence between the old feature branch tip and `main`.**
  - New `liverig-setup-tool/` Ableton Extension: right-click any audio/MIDI track in Live Beta → "Configure LiveRig…" → modal form for rig name, KBD1-4 track bindings/bank size/buttons/faders/CC range, stems (label/track/default volume), max patches + animation ms.
  - Writes its working copy to `context.environment.storageDirectory/rig_config.json` (the SDK sandbox forbids writing directly to `~/Desktop/liverig/`).
  - `LiveRig_Wired_Start.sh` extended with a sync step: on every launch, compares mtimes of the extension's storage copy vs. `~/Desktop/liverig/rig_config.json` and `shutil.copy2`s the newer one over — this is the real (non-clipboard) handoff mechanism, decided 2026-06-26.
  - **Bug found & fixed (commit `b5fb8a2`):** the modal dialog's initial-data payload was spliced into `interface.html` as raw, un-encoded JSON (with literal quotes), causing a silent JS syntax error inside the sandboxed webview — dialog hung forever on "Loading…" with zero visible error anywhere. Fix: `encodeURIComponent()` the JSON payload before splicing it into the document, on top of the existing whole-document `encodeURIComponent()` for the `data:` URI (double-encoding pattern, standard for nesting URI-encoded content).
  - **Git history note:** Claude Code's first commit (`57826d2`) was built on a stale/diverged base; reconciled onto the correct tip as `a8dc1fe` (same file content, correct parent) before the fix (`b5fb8a2`) landed on top. Current branch tip: `b5fb8a2`.
  - **Verified working 2026-06-26:** saved a real config via the modal (KBD1-4 → MAIN KEYS/TOP KEYS/KEYS L/KEYS R, 8 stems DRUMS/PERC-LOOP/BASS/GTR/AUX/FX/VOCALS/LEAD VOCALS) → confirmed it landed byte-for-byte in `~/Desktop/liverig/rig_config.json` via the launcher's sync step (matching mtimes/size, content inspected directly).
  - **Outstanding before merge:** confirm `LiveRig.py` actually re-reads the synced config in a live Ableton session. As of last check, `Log.txt`'s last "rig_config loaded" line predates the new save — `LiveRig.py` only reads the config at Remote Script init, not live, so a Live restart (or Control Surface dropdown toggle to None and back) is required to pick it up. David is restarting Live now to retest; next step is re-checking `Log.txt` for a fresh "rig_config loaded… (4 keyboards)" line timestamped after the save, and confirming the iPad controller UI reflects the new labels/stems after a hard page reload.
  - **Hard constraint:** Ableton Live 12 Beta is currently the only Live install David can use for Extensions SDK work (just auto-updated to 12.4.5b5).

## On the horizon

- Both branches (`refactor/rig-config`, `feature/extensions-sdk-setup`) are merged to `main`. No open PRs.
- **>4 keyboard support:** requires restructuring static page/tab markup in `live_rig_3_controller.html` — deferred, no timeline.
- See `BRANCHING_STRATEGY.md` for fork points, merge order, and conflict zones (historical reference now that both branches are merged).

## Key learnings & principles (additions 2026-06-30)

- **JavaScript temporal dead zone (TDZ):** `let` and `const` variables are hoisted but NOT initialized — accessing them before their declaration line throws `ReferenceError: Cannot access 'X' before initialization`. This can crash an entire `<script>` block silently if the throw happens in top-level code. Static HTML (like section headers) still renders but any JS-generated DOM is missing. Always check Chrome DevTools Console first when a dynamically-built section is blank but the page otherwise loads.
- **`/private/tmp` vs `/tmp` on macOS:** `/tmp` is a symlink to `/private/tmp`. Writing via `/tmp/` path can fail silently (particularly with `sed >` redirection). Always use `/private/tmp/` directly for reliable writes.
- **LiveRig bundle is source of truth:** editing `~/Desktop/liverig/live_rig_3_controller.html` is not enough — the bundle Resources file must also be updated, or the change will be overwritten on next app launch. Use Python `shutil.copy2()` to update both atomically.
- **Chrome extension's `read_console_messages` is the fastest debug path** for JS errors in the served page — far faster than asking the user to open DevTools manually.

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

## Master page — FX Return faders + automatic mute/solo (2026-06-30, commit `bfaccdb`)

### What was built
Master page now shows **11 channels** (was 8 + a STEMS nav button):
- KBD 1-4 (dynamic labels from `kbdMasterLabel()`)
- CLICK, GUIDE, LOOPS (aux row, CH5)
- **REV 1, REV 2** (return tracks A+B, purple `#9060e0`) — NEW
- **DLY 1, DLY 2** (return tracks C+D, orange `#e09030`) — NEW

STEMS quick-nav button removed from Master page (saved as commented code in `buildMaster()` for future use).

### CC scheme for FX returns (CH7, 0-indexed channel 6)
- Faders: CC 1-4 (REV1, REV2, DLY1, DLY2)
- Mutes: CC 5-8
- Solos: CC 9-12
Registered in `LiveRig.py`'s `build_midi_map()` — no Cmd+M mapping required.

### Automatic mute/solo via Remote Script
All KBD and stem track mute/solo is now handled via `build_midi_map()` + `_dispatch_cc()` in `LiveRig.py` — **no Cmd+M mapping needed by the user**. Confirmed working by David.

`build_midi_map()` registers:
- CH1-4 CC1+CC2 (KBD mute/solo)
- CH6 stem mutes/solos (CC range dynamic from STEM_COUNT)
- CH7 CC1-12 (FX return vol+mute+solo)

`_dispatch_cc(channel, cc, val)` routes each incoming CC to the correct Ableton track object via `song.return_tracks[ri]` for returns (A=0, B=1, C=2, D=3).

### CSS additions
```css
.fill-fx-rv{background:#9060e0;}
.fill-fx-dly{background:#e09030;}
.fx-rv{color:#9060e0;}
.fx-dly{color:#e09030;}
```

### Critical JS TDZ bug found and fixed (commit `5a22d4f`)
`buildMaster()` was never being called — the entire script crashed at line 1063 before reaching the call site. Root cause: `const STEM_COUNT = (RIG_CONFIG.stems || []).length || 8` referenced `let RIG_CONFIG` which was declared 350 lines later (temporal dead zone). The "MASTER VOLUMES" label was static HTML so it appeared, but the dynamic fader columns were never appended.

Fix: moved `const RIG_CONFIG_DEFAULT`, `let RIG_CONFIG`, and the XHR load try/catch block from line ~1412 to just before the STEMS section (~line 1062), so `RIG_CONFIG` is declared before any top-level code references it. `buildMaster()` now executes, `master-faders-row` gets 11 children, grid is `repeat(11, 1fr)`. Confirmed in Chrome DevTools: no JS errors, all 11 channels visible.

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
- **Cleanup done, method body deleted (commit `4e971c3`):** the `_dump_looper_params` method (both the call site, removed earlier, and the now-dead method body) is gone from `LiveRig.py`.

## >4 keyboard support — built & shipped 2026-06-30 (commit `4e971c3`)

The 4-keyboard ceiling is gone. Previously it was baked into three places: the controller HTML's static `page-4`..`page-7` divs + 4-tab bar, AND the assumption that MIDI channel index == KBD slot index (hardcoded `ch1-4` in both the HTML and `LiveRig.py`'s `build_midi_map`/`_dispatch_cc`). Fixed all three, config-driven end to end:

- **Channel assignment (shared logic, kept in sync across JS and Python):** reserved channels (0-indexed in Python, 1-indexed in JS) = CH5 (aux Click/Guide/Loops), CH6 (stems), CH7 (FX returns), CH10 (pads), CH16 (transport). A keyboard's MIDI channel comes from `rig_config.json`'s per-keyboard `"midiChannel"` field (1-indexed) if present, else auto-assigned by walking ch1-16 skipping reserved ones. KBD1-4 land on ch1-4 either way (unchanged). KBD5 → ch8, KBD6 → ch9, KBD7 → ch11, ... up to KBD11 → ch15 (11 keyboards max with today's reserved set).
  - JS: `kbdDefaultChannel()`/`kbdChannel()` in `live_rig_3_controller.html`.
  - Python: `_default_kbd_channel_0idx()`/`_kbd_channels_from_config()` in `LiveRig.py`, feeding `self._kbd_channels` + `self._kbd_channel_to_index` (used by `build_midi_map()` and `_dispatch_cc()`, replacing the old hardcoded `range(4)` / `0 <= channel <= 3` checks).
  - Verified both implementations produce identical output for indices 0-10: `[1,2,3,4,8,9,11,12,13,14,15]`.
- **`rig_config.json`:** added explicit `"midiChannel": 1/2/3/4` to David's real 4 keyboards (same values as the old implicit default — no behavior change, just now visible/editable).
- **`live_rig_3_controller.html`:** `KBD_COUNT` is no longer `Math.min(4, ...)` — it's just `RIG_CONFIG.keyboards.length`. New keyboards beyond the static first 4 get a dynamically created tab + page (`ensureDynamicKbdTabsAndPages()`, inserted right after the "Kbd 4" tab, called before `applyTabOrder()`/`attachTabHandlers()` so drag-reorder still works on them) and an auto-generated color (`kbdColor()` — first 4 keep their exact original hex values, 5+ use HSL generation). `buildKbdPage()`, `buildMaster()`'s KBD columns, both Patches-page PC-send loops, and `updateKbdTabs()` were all switched from assuming "channel == index + 1" / "exactly 4 keyboards" to using `kbdChannel(k)`/`kbdPageId(k)`/`KBD_COUNT`. New generic CSS classes `.kbd-dyn`/`.fill-kbd-dyn` (color via inline `--kbd-c`/`--kbd-c-dim` custom properties) handle any keyboard count without needing new CSS per index.
- **Verified via a headless jsdom test** (not just syntax-checked): the real 4-keyboard `rig_config.json` renders byte-identical to before (12 tabs, 11 Master columns, same colors/channels — zero regression). A synthetic 6-keyboard config correctly added 2 new tabs/pages positioned right after "Kbd 4", with correct auto-assigned channels (ch8, ch9) and distinct colors, and 13 Master columns (6 KBD + 3 aux + 4 FX).
- **Scope note:** this removes the ceiling but doesn't add a way to *provision* a 5th+ keyboard — that still means hand-editing `rig_config.json` (or waiting on the Extensions SDK setup-tool modal to grow a channel/count field, see pending task below) plus having an actual track for it in Live.

## Pending tasks (carried forward, not yet superseded)

~~Remove the temporary `_dump_looper_params(0)` diagnostic call~~ — done, call site and now the dead method body are both gone (`4e971c3`).
~~Open/merge PR for `feature/extensions-sdk-setup` → `main`~~ — done, merged as `c4c9430`.
~~Restructure controller HTML markup to support >4 keyboards~~ — done, see section above (`4e971c3`).

1. Decide whether to delete superseded `SESSION_BACKUP.md` from repo root (archive copy already safe at `~/Documents/LiveRig_Archive/SESSION_BACKUP_2026-05-01.md`). Still present at repo root as of 2026-06-30.
2. Build "blue hand" mode — KBD pages auto-bind to currently-selected track's first 8 device params.
3. Multi-computer routing UI (Option A architecture) — when needed.
4. Extensions SDK setup-tool modal (`liverig-setup-tool/`) has no field yet for per-keyboard `midiChannel` or for adding a 5th+ keyboard slot — currently requires hand-editing `rig_config.json` to actually use the new >4 keyboard support. Natural next step if David wants to provision a real 5th keyboard through the modal instead of by hand.
5. **Still not deleted — needs David's own Terminal, not this session:** stray local branch `claude/keen-mestorf-aedfa5` + its worktree under `.claude/worktrees/keen-mestorf-aedfa5` (diff vs. `main` is empty, safe to delete). The sandboxed session's filesystem bridge can't unlink files inside `.git/worktrees/*` (`git worktree remove --force` fails with "Operation not permitted" from that side). Run from David's Mac Terminal:
   ```
   cd ~/Desktop/liverig
   git worktree remove --force .claude/worktrees/keen-mestorf-aedfa5
   git worktree prune
   git branch -D claude/keen-mestorf-aedfa5
   ```

## Known sandbox quirk: stale git locks (2026-06-30)

The Claude session's filesystem bridge to `~/Desktop/liverig` sometimes can't unlink git's internal lock files (`index.lock`, `HEAD.lock`, `refs/remotes/origin/*.lock`) — commands fail with "Operation not permitted" instead of actually removing them, and even read-only commands like `git status` can leave one behind. When a git command from a Claude session fails with "Another git process seems to be running" / "Unable to create '.../index.lock'", the fix is for David to run, from his own Terminal (not through Claude):
```
cd ~/Desktop/liverig
rm -f .git/index.lock .git/HEAD.lock .git/refs/remotes/origin/main.lock
```
This is a sandbox-mount limitation, not repo corruption — David's local git is always fine underneath it. GitHub push access itself works fine once a PAT is configured as a git credential inside the session (done 2026-06-30, stored at `~/.git-credentials` inside the sandbox — separate from David's own Mac Keychain PAT).

## How to resume in a new chat

1. Read this file first — it's the live state, not `SESSION_BACKUP.md`.
2. The Master page is fully working as of 2026-06-30: 11 channels (KBD 1-4, CLICK/GUIDE/LOOPS, REV 1/REV 2/DLY 1/DLY 2), mute/solo automatic via Remote Script. No open regressions.
3. >4 keyboard support shipped 2026-06-30 (`4e971c3`) — see dedicated section above. KBD_COUNT is dynamic now; adding a real 5th+ keyboard still means hand-editing `rig_config.json` until the setup-tool modal grows the field for it.
4. Continue from "Pending tasks" above — top items done (looper diagnostic cleanup incl. dead method, extensions-sdk-setup PR, >4 keyboard restructure); next up is the `SESSION_BACKUP.md` deletion decision, "blue hand" mode, and the stray branch/worktree cleanup (needs David's own Terminal, see note above).
4. Respect channel isolation and architectural decisions listed above.
5. Don't reintroduce removed features (Record/Punch/Overdub on Setlist, STEMS nav button on Master, etc.) without confirming with David first.
6. Use `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` for Ableton log checks — not the old 12.3.8 folder.
7. **Deployment pipeline**: edit `~/Desktop/liverig/` source → copy to bundle Resources → restart LiveRig app. Check `/private/tmp/liverig_controller_served.html` timestamp to confirm the menubar script re-generated the served file. Use Chrome extension's `read_console_messages` to verify no JS errors before telling David to check the iPad.
