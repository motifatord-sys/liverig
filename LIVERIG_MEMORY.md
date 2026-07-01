# LiveRig Memory — Live, Writable State

> This file replaces `SESSION_BACKUP.md` (stale as of 2026-05-01) as the canonical project memory. It lives in the repo so it's read/write for Claude every session — no manual paste-in required. Updated on request ("Jesus Saves") or at natural session boundaries.

**Last updated:** 2026-07-01 (**Binding-status validation shipped, all 3 parts — commits `a43eb5d` + `dbdc579`** — see dedicated section below; **LiveRig.app's launcher script now auto-deploys the Remote Script on every launch, closing the deployment gap below for good** — plus a new `scripts/build_dmg.sh` for a proper distributable installer, pending David running it once on his own Mac to re-sign + package; ONBOARDING.md added — full install-to-operation walkthrough + honest gap list; Found and fixed the underlying deployment gap: `LiveRig.py` was stale at the real Ableton install path for most of this session's work, now synced; Bidirectional volume feedback added for KBD/Stems/FX-Returns + Click/Guide automation scaffolded pending real track names, commit `1674e86`; Master/Stems volume faders fixed to control Ableton directly, commit `9a5233d`; Clips page rebuilt for native Live API clip control + accurate Session View state, commit `867820e`; 4 UI fixes — Stems fader sizing, Master LOOPS fader removed, Clips play-icon emoji replaced, Clips real clip names — commit `4954ee8`; Blue Hand mode shipped, commit `727a6c7`; >4 keyboard support shipped, commit `4e971c3`; dead `_dump_looper_params` method deleted, commit `4e971c3`)

## Binding-status validation — shipped 2026-07-01 (commits `a43eb5d`, `dbdc579`)

David's question: with the Setup Tool letting you assign tracks to faders directly, isn't binding by track name redundant? Answer stayed the same as reasoned through earlier today — Extensions SDK `Handle`s are session-ephemeral, track *name* is the only thing that survives into a re-opened `.als` file, so name-binding isn't redundant, it's the only thing that CAN persist. But two real gaps existed around it, both closed now, in three parts (David chose "all three" when asked how much to build):

1. **`LiveRig.py`** — `_resolve_track_binding()` now returns `(index_or_None, status)` instead of just an index. String-name matching collects ALL matches instead of stopping at the first, so a duplicate track name is now detected (`BIND_STATUS_AMBIGUOUS`) instead of silently picking one. New constants: `BIND_CAT_KBD/STEM/LOOPER/AUX` (0-3) and `BIND_STATUS_OK/OK_POSITIONAL/UNBOUND/AMBIGUOUS/EMPTY/FALLBACK_MISMATCH` (0-5). New `FB_BINDING_STATUS = 0x56` SysEx code, diff-cached via `_note_binding_status()` so it only fires on change, plus `_emit_all_binding_statuses(force=True)` wired into `_emit_full_state()` for a full resync whenever the iPad reconnects.
2. **`live_rig_3_controller.html`** — new amber/red ⚠ `bind-warn-badge`, wired into `buildMaster()` (kbd/aux columns only — FX returns are fixed tracks, never name-bound), `buildStems()`, and `buildLooper()`. `updateBindingIndicator(catInt, idx, status)` maps the category int straight to `BIND_CAT_NAMES = ['kbd','stem','looper','aux']` — index-for-index identical to the Python constants, checked explicitly.
3. **`liverig-setup-tool/src/interface.html`** (Setup Tool modal) — non-blocking warning banner + amber-outlined `<select>`s for the same two problems, caught at config time instead of only at runtime: (a) the Live Set itself has two tracks sharing a name, (b) this config binds the same track name to more than one role (e.g. a keyboard and a stem both pointing at "DRUMS"). Save is never disabled — there can be legitimate reasons to leave a duplicate-named track's binding as-is. `syncFromSelect()` now calls `render()` so the banner/highlights update live as bindings change.

**Mid-session catch, same class of gap as before:** when starting part 3, found the deployed `LiveRig.py` (both `~/Music/Ableton/User Library/Remote Scripts/LiveRig/` and `LiveRig.app/Contents/Resources/LiveRig/`) was STALE — missing all of part 2's work, 148 lines of diff. This happened because part 2 was written to the repo copy only and never re-synced before part 3 started. Re-copied to both locations, confirmed byte-identical via diff before committing. **Takeaway reinforced: re-sync `LiveRig.py` to both deployed locations as part of the SAME change, not as a follow-up step** — don't let repo-only edits sit even mid-session.

**Verification done:** standalone 10-case test harness for `_resolve_track_binding` (all passed, done before compaction), `node --check` on both HTML files' extracted `<script>` blocks, category-int alignment checked line-by-line against `LiveRig.py`'s `BIND_CAT_*` constants, full `tsc --noEmit` + `tsx build.ts --production` + `extensions-cli package` for the Setup Tool (all clean, fresh `.ablx` built). **Not yet verified:** live in an actual Ableton session with a real duplicate-name/double-assignment scenario — next time David's in Live, worth deliberately misconfiguring one track to confirm the badge/banner actually appear end-to-end.

## Remote Script deployment gap — found & fixed 2026-07-01 — READ THIS FIRST

**This was the actual root cause of "the faders still aren't controlling Ableton" after the fixes below.** The Remote Script (`LiveRig.py`) has its OWN separate install location that is completely independent of both the git repo and the LiveRig.app bundle:
```
~/Music/Ableton/User Library/Remote Scripts/LiveRig/LiveRig.py
```
Editing `~/Desktop/liverig/LiveRig/LiveRig.py` (the repo copy) and committing/pushing to GitHub does **NOT** touch this file. Nothing auto-syncs it — there is no launcher-script copy step like the HTML/bridge have via the LiveRig.app bundle. Found by diffing the two files 2026-07-01: the installed copy was 1424 lines vs. the repo's 2099 — missing >4 keyboard support, Blue Hand mode, native Clips control, and the volume-fader fixes, i.e. essentially all of this session's Remote Script work. On top of that, `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` showed Live hadn't even been relaunched since 2026-06-29 18:43 — before any of it — so even the stale copy wasn't freshly reloaded.

**Fixed 2026-07-01:** copied the current repo `LiveRig.py` (and `rig_config.json`, cosmetic only since `_load_rig_config` always prefers the `~/Desktop/liverig/` copy anyway) to the real install path. `__init__.py` was already identical, untouched.

**This is now a required step, every session, whenever `LiveRig/LiveRig.py` changes** — treat it exactly like the LiveRig.app bundle Resources sync below, just a different destination:
```
cp ~/Desktop/liverig/LiveRig/LiveRig.py "~/Music/Ableton/User Library/Remote Scripts/LiveRig/LiveRig.py"
```
Then David needs to restart Ableton Live (the **12.4.2 Suite** install — not the Beta) or toggle the Control Surface dropdown to `None` and back to `LiveRig` in Settings → Link, Tempo & MIDI, since Python Remote Scripts are only (re-)imported at that point, never live. Confirm via a fresh `"LiveRig Remote Script loaded."` line in `Log.txt` timestamped after the restart.

**Access:** this session now has `~/Music/Ableton/User Library/Remote Scripts` connected (requested 2026-07-01 alongside `~/Library/Preferences/Ableton` for the version-folder check) — no need to ask David to do this copy by hand going forward, do it directly as part of shipping any `LiveRig.py` change.

**Permanently closed 2026-07-01 (same day) — LiveRig.app's launcher script now auto-deploys the Remote Script on every launch.** David asked for a proper installer/DMG so this class of gap can't recur for an end user. Rather than build a whole separate installer mechanism, extended the exact same pattern the launcher script already uses for HTML/bridge/menubar:
- `/Applications/LiveRig.app/Contents/Resources/LiveRig/` now contains `LiveRig.py` + `__init__.py` (previously absent from the bundle entirely — this subfolder didn't exist before today).
- The launcher script (`Contents/MacOS/LiveRig`) now also does `mkdir -p` + `cp -f` of those two files into `~/Music/Ableton/User Library/Remote Scripts/LiveRig/` on every launch, exactly like the existing HTML/bridge/menubar copies — bundle Resources is the source of truth, unconditional overwrite.
- Difference from the other copies: it first `cmp -s`s old vs. new content, and only if they actually differ does it pop an `osascript` dialog telling David to restart Ableton (or toggle the Control Surface dropdown) — a plain file copy does NOT make Ableton reload it, so this can't be fully automated away, but the dialog at least makes the "you still need to restart Live" step impossible to miss silently, unlike before.
- Verified the change/no-change detection logic with an isolated 4-case dry run (fresh install / repeat launch / content updated / repeat launch again) before touching the real bundle — all four behaved correctly.
- **Whenever `LiveRig/LiveRig.py` changes in the repo going forward, also re-copy it into `/Applications/LiveRig.app/Contents/Resources/LiveRig/LiveRig.py`** (in addition to the direct-to-Remote-Scripts sync in the section above) — the bundle copy is what makes this survive a fresh machine setup, not just this session's live one.
- **Code-signing caveat, action needed from David:** modifying the launcher script and adding a new Resources subfolder invalidates the app's existing ad-hoc code signature (`_CodeSignature/`), which this project has hit before (see the 2026-06-29 TCC/Desktop-permission entry below). `codesign` and `hdiutil` are macOS-only — unavailable in this session's Linux sandbox — so David needs to run `scripts/build_dmg.sh` (added this same commit) himself at least once, which re-signs the app (`codesign --force --deep -s -`) before packaging. **Not yet run/confirmed** — top item until David does this.
- **`scripts/build_dmg.sh`** (new): re-signs `/Applications/LiveRig.app`, stages it alongside an `/Applications` symlink and a short Read Me, and runs `hdiutil create` to produce `dist/LiveRig-Installer.dmg`. `dist/` and `*.dmg` are gitignored (build output). Run it again any time the app bundle's contents change and a fresh installer is wanted.

## App bundle architecture — CRITICAL deployment fact

- `/Applications/LiveRig.app/Contents/MacOS/LiveRig` is a **shell launcher script**, NOT a binary.
- On **every launch**, it runs `cp -f "$RESOURCES/live_rig_3_controller.html" "$SUPPORT/"` and similarly for `liverig_bridge_wired.py` and `liverig_menubar.py`.
- **Bundle Resources (`/Applications/LiveRig.app/Contents/Resources/`) is the true source of truth** — `Application Support/LiveRig/` always gets overwritten.
- To deploy HTML/Python changes: update `~/Desktop/liverig/` source files, copy to bundle Resources (use a Python script — cp and rsync silently appear to succeed but the launcher's cp overwrites on next launch), then restart the app.
- `liverig_menubar.py` reads `live_rig_3_controller.html` from Application Support, injects `{{BRIDGE_HOST}}` → writes to `/private/tmp/liverig_controller_served.html` — this is what the HTTP server (port 8080) actually serves.
- **Always use `/private/tmp/` not `/tmp/`** — macOS symlinks `/tmp` → `/private/tmp` but `sed >` file writes through `/tmp` can silently fail. All paths in `liverig_menubar.py` use `/private/tmp/` (fixed commit `44f365d`).
- **This bundle mechanism covers the HTML and bridge only, NOT `LiveRig.py`** — see "Remote Script deployment gap" section above for the separate (and previously missed) sync step that file needs.

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
  - **Hard constraint:** Ableton Live 12 Beta is currently the only Live install David can use for Extensions SDK work (the Extensions SDK itself isn't fully released yet, so David runs whatever the latest beta build is). Auto-updates frequently — was `12.4.5b5`, now `12.4.5b6` as of 2026-07-01. **Don't hardcode a beta version number anywhere** — always check `~/Library/Preferences/Ableton/` for the newest `Live 12.4.5bN` folder by mtime before assuming which one is current.
  - **Two separate Live installs, two separate prefs folders — don't mix them up:** the main rig (`LiveRig.py` Remote Script, day-to-day playing/testing) runs on the stable **Ableton Live 12 Suite**, prefs folder `Live 12.4.2` (not auto-updating as fast, unaffected by beta churn). The **Ableton Live 12 Beta** app is Extensions SDK work only, prefs folder is whichever `Live 12.4.5bN` is newest. Confirmed directly with David 2026-07-01 after he flagged that a newer-looking folder existed and I couldn't see it (only had `Live 12.4.2` mounted) — requested and got access to the parent `~/Library/Preferences/Ableton/` folder to check going forward.
  - **Two install modes for the extension itself — dev-mode vs. packaged, and this project had only ever used the former (found 2026-07-01):** `npm start` (`extensions-cli run`) hot-loads the extension into whichever Live session is currently running — it does NOT persist across a new Live session, has to be re-run every time, and is what caused David's "right-click menu disappeared" question. `extensions-cli package` (confirmed via its own `--help`, not guessed) builds a `.ablx` archive — a plain zip of `manifest.json` + the built `dist/extension.js` — which installs persistently the way Ableton's own Extensions FAQ describes: Live 12 → Preferences → Extensions → drag the `.ablx` into the Extension area (or drag-and-drop directly into Live). **Packaged extensions require Developer Mode OFF and no `npm start` process running to actually appear** — the two modes are mutually exclusive at any given moment, per Ableton's FAQ.
  - **Added 2026-07-01 (commit `881a29e`):** new `npm run package` script in `liverig-setup-tool/package.json` — production build (minified, no sourcemap) + `extensions-cli package . -o dist/liverig-setup-tool.ablx`. Built and verified once: 32.7KB `extension.js`, zip contents confirmed to be exactly `manifest.json` + `dist/extension.js`, no dev artifacts. `dist/` and `*.ablx` are already gitignored (correctly — build output, not source), so the binary itself isn't committed; run `npm run package` fresh whenever `src/extension.ts` changes and a persistent install is wanted. **Not yet confirmed working end-to-end by David** (i.e., dragged into Live with Developer Mode off, right-click menu appears without needing `npm start`) — next step.

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
- **Bug found & fixed while building Blue Hand (commit `727a6c7`):** the client-side SysEx feedback handlers for fb 0x40 (macro/param value), 0x41/0x42 (param list begin/end), 0x43 (device info), 0x44 (KBD color), 0x45 (KBD name) were still hardcoded to `kbdIdx < 4`, silently dropping feedback for any KBD5+ that this section claimed to support end-to-end. Fixed to `KBD_COUNT`. One remaining cosmetic gap, not yet fixed: KBD5+ live Ableton track-color changes (fb 0x44) don't repaint the dynamic `--kbd-c` elements the way KBD1-4's global `--k1..--k4` vars do — control is unaffected, just the live color-follow is KBD1-4-only for now.

## Blue Hand mode — built & shipped 2026-06-30 (commit `727a6c7`)

Global toggle (new "HAND" button in the status bar, next to PANIC). While active, whichever KBD page is currently on screen stops reflecting its fixed `defaultTrackBinding` and instead directly drives whatever track is selected in Ableton right now — specifically that track's first device's first 8 parameters (`device.parameters[1:9]`, ANY device type, not just Racks — safe to do generically here because this is a brand-new control path this script owns outright, not layered on top of the user's own Cmd+M mappings like the normal KBD1-4 faders are).

- **Dedicated channel, not shared with any KBD slot:** `BLUE_HAND_CHANNEL_0IDX = 14` (CH15) in `LiveRig.py`, added to the reserved-channel set in both Python and JS so keyboard auto-assignment (see section above) never collides with it (max auto-assignable keyboards drops from 11 to 10 as a result). CC10-17 on that channel are *always* registered via `build_midi_map` — toggling Blue Hand on/off doesn't touch MIDI Map registration, it's a no-op in `_dispatch_cc` whenever no KBD slot has opted in (`self._blue_hand_kbd_idx is None`), so no `request_rebuild_midi_map()` juggling needed.
- **New SysEx:** inbound `SX_BLUE_HAND_ON`/`SX_BLUE_HAND_OFF` (0x50/0x51, value = kbd_idx) drive `self._blue_hand_kbd_idx` + `_rebind_blue_hand_listeners()`/`_unbind_blue_hand_listeners()`. Re-targets automatically on Live's selected-track-changed event (`_on_selected_track_changed`), not just on toggle — so clicking a different track in Live while active re-binds live with zero iPad interaction. `_dispatch_cc` also re-resolves the selected track fresh on every incoming CC (not just via the listener rebind) so a fast track-click-then-fader-move sequence can't land on a stale target.
- **Feedback reuses the existing macro-value pipeline** (`FB_MACRO_VALUE` 0x40, same wire format, keyed by kbd_idx) — zero new client-side rendering code needed for the fader values themselves.
- **New `FB_KBD_DEVICE` (0x43) + `_emit_kbd_device()`:** completes a previously half-built, fully orphaned feature — the JS side already had `updateKbdDeviceHeader()` wired to fb 0x43 from an earlier session, but no DOM element existed to receive it and Python never emitted it. Added the missing `<div id="kbd-device-header-${k}">` to every KBD page and the Python emitter; now called from `_rebind_macro_listeners()` (so ALL KBD pages show their bound device name, fixed-track or not) and from `_rebind_blue_hand_listeners()` (prefixed `"BLUE HAND → "` client-side when that slot is the active one).
- **Cross-talk avoidance:** normal per-slot macro listeners (`_rebind_macro_listeners`) are fully unbound while Blue Hand is active for ANY slot (not just the affected one) via `_unbind_macro_listeners()` on `SX_BLUE_HAND_ON`, and restored via a full `_rebind_macro_listeners()` on `SX_BLUE_HAND_OFF` — avoids two feedback sources racing to update the same kbd_idx's fader.
- **Client-side (`live_rig_3_controller.html`):** `toggleBlueHand()`, `syncBlueHandToActivePage()`, `currentActiveKbdIndex()` — the last one maps whatever page is currently `.active` back to a KBD index (or null if you're not on a KBD page at all). Hooked into `switchToPage()` so changing KBD tabs while Blue Hand is on transparently sends a fresh `blue_hand_on` for the new tab's index; navigating to a non-KBD page sends `blue_hand_off` (pausing it, not disabling the global toggle) until you land back on a KBD page.
- **`liverig_bridge_wired.py`:** new `blue_hand_on`/`blue_hand_off` JSON message types, same passthrough pattern as `loop_rec` etc.
- **Verified via jsdom** (not just syntax-checked): simulated toggling Blue Hand on while viewing KBD1, switching to KBD2, navigating to Master, then back to KBD3, then toggling off — produced the exact expected call sequence (`on:0 → on:1 → off:1 → on:2 → off:2`).
- **Not yet confirmed live by David** — next step is reloading the Remote Script (Live restart or Control Surface dropdown toggle) and testing on the iPad: toggle HAND on, click around different tracks in Live, confirm the currently-viewed KBD page's faders/header follow.

## Four UI fixes — shipped 2026-06-30/07-01 (commit `4954ee8`)

David reported these together after seeing the live UI:

1. **Stems (tab 2) faders wrong size vs. Master.** Root cause: `buildStems()` had a leftover 2-row-grid fallback for `STEM_COUNT > 8` (David's real rig has 10 stems), which halved each fader's height. Fixed to always render a single row (`gridTemplateColumns: repeat(STEM_COUNT,1fr)`, `gridTemplateRows: '1fr'`), matching how Master already laid out its columns.
2. **Master page LOOPS fader removed** — no longer needed (loopers have their own dedicated Looper-device UI/page). `buildMaster()`'s `CHANNELS` array entry for LOOPS (ch:5, cc:22, muteCc:26, soloCc:30) deleted; Master now renders 10 columns instead of 11.
3. **Clips page transport-play icon was a literal Unicode "▶" emoji-style glyph**, inconsistent with the rest of the app's inline-SVG icon style. Replaced with an inline SVG triangle matching the existing per-track play icons (`<svg viewBox="0 0 20 20" ...><polygon points="4,3 16,10 4,17"/></svg>`).
4. **Clips page tiles didn't show clip names.** This was a fully-built-but-orphaned feature from an earlier session: `updateClipNamesFromLive()`/`updateClipTrackHeaders()` existed client-side but were wired to a dead M4L/HTTP-JSON data path (`m4l.liveClips`/`m4l.liveTracks`) that nothing ever actually populated. Rather than resurrecting the M4L device (against this project's established direction away from M4L), built a fresh Remote-Script-based data source: `LiveRig.py` polls the first `CLIP_TRACKS`(8) × `CLIP_SCENES`(8) Session View grid at ~1Hz (`_scan_clip_grid`/`_poll_clip_grid_tick`), diffs against a cache, and emits new SysEx codes `FB_CLIP_TRACK_NAME` (0x50)/`FB_CLIP_INFO` (0x51) only for cells that changed. This is what fed the pre-existing render functions for the first time. (This whole pipeline was superseded/upgraded the next day — see "Clips page: native Live API control" below.)

## Clips page: native Live API clip control + accurate Session View state — shipped 2026-07-01 (commit `867820e`)

David asked to go beyond just showing clip names: make the Clips page **directly fire/stop real Ableton clips** (not fake MIDI notes/CCs requiring manual Cmd+M mapping of all 64 slots) and **reflect real playing/triggered/recording state** the way Ableton's own Session View does. Researched the Live Object Model (`docs.cycling74.com/apiref/lom/` — ClipSlot, Clip, Track, Song classes) before building, matching this project's established research-then-build pattern.

- **New inbound SysEx (`LiveRig.py`):** `SX_CLIP_FIRE` (0x52, value = `(scene_idx<<3)|track_idx`) → `ClipSlot.fire()`; `SX_CLIP_STOP_TRACK` (0x53, value = track_idx) → `Track.stop_all_clips()`; `SX_CLIP_STOP_ALL` (0x54) → `Song.stop_all_clips()`. All three go straight through the Live Object Model — no Ableton MIDI Map / Cmd+M mapping of individual clip slots needed at all anymore.
- **Accurate state via `Track.playing_slot_index`/`Track.fired_slot_index`** (one int each per track, per the LOM docs) instead of walking every clip's `is_playing` — this is the same mechanism Ableton's own Session View grid uses internally, and is what makes the "triggered" (blinking, about to play/stop) state possible for the first time. `is_recording` is still a per-clip read (`Clip.is_recording`), but only for the one slot that's actually `playing_slot_index` on that track (only one clip per track can be active). `_scan_clip_grid` rewritten accordingly.
- **`FB_CLIP_INFO` (0x51) wire format changed** from two separate booleans (has_clip, is_playing) to a single packed flags byte: bit0=has_clip, bit1=playing, bit2=triggered, bit3=recording. Client-side parsing in `onRemoteScriptFeedback` (fb 0x51 handler) updated to match.
- **Poll rate tightened from ~1Hz to ~3.3Hz** (`schedule_message(3, ...)` instead of `10`) now that this page is used interactively for firing clips — a blinking "triggered" state needs to show up in well under a second, not up to a full second later.
- **`liverig_bridge_wired.py`:** new `clip_fire`/`clip_stop_track`/`clip_stop_all` WebSocket→SysEx passthroughs, same pattern as the existing `blue_hand_on`/`scene_fire` handlers.
- **`live_rig_3_controller.html`:** `clipLaunch(scene,track)`, `clipStopTrack(track)`, `clipStopAll()` rewritten to send native WebSocket JSON messages (matching the pattern `clipScene()` already used) instead of raw MIDI notes/CCs. New visual state 4 = "triggered" with a fast blink CSS animation (`clip-trigger-blink`, distinct from the existing slower `playing`/`recording` pulses) — this is Ableton's own "about to launch/stop" blink. `updateClipNamesFromLive()` rewritten to derive the displayed state from Live's real flags with the correct precedence: recording > playing > triggered > stopped(loaded) > empty. Clip taps also get an **optimistic** triggered-state flash immediately on tap (confirmed/corrected by the next ~300ms poll), so the UI feels responsive even before Live's own state updates propagate back.
- **Verified via jsdom + Node unit tests** (not just syntax-checked): confirmed the state-precedence logic (recording/playing/triggered/stopped/empty) picks the right CSS class + label for each combination of flags, and confirmed the scene/track bit-packing is symmetric — `(scene<<3)|track` encoded client-side unpacks back to the exact same `(scene_idx, track_idx)` pair server-side for all 64 grid positions.
- **Not yet confirmed live by David** — next step is reloading the Remote Script (Live restart or Control Surface dropdown toggle) and testing on the iPad: tap a clip and confirm it actually launches in Ableton, watch the blink-then-play transition, test track-stop and stop-all, and confirm an already-playing clip shows recording state correctly if armed+overdubbing.

## Master/Stems volume faders fixed — shipped 2026-07-01 (commit `9a5233d`)

David reported: "the faders on the Masters page with the exception of REV1/2 DLY1/2 aren't controlling the faders in Ableton. Same goes for the faders on the stems page."

**Root cause:** only mute/solo (KBD CC1/2 per keyboard channel; Stem CC N+1..3N on ch6) and FX return vol+mute+solo (CC1-12 ch7) were ever registered in `build_midi_map()`/handled in `_dispatch_cc()`. KBD volume (CC7) and Stem volume (CC1..N on ch6) were never direct-CC — they silently depended on the user manually Cmd+M-mapping each one to the track's mixer volume inside Ableton, which is exactly the kind of fragile per-Live-Set manual setup this project has been steadily eliminating everywhere else (mute/solo, FX returns, Looper state/quantization are all already direct). That's why REV/DLY kept working (already direct-CC) while everything else didn't.

**Fix:** extended the exact same pattern already proven for FX return volume (`ret_tracks[ri].mixer_device.volume.value = val / 127.0`) to KBD and Stem tracks:
- `build_midi_map()` now also forwards CC7 per KBD channel and CC1..N on ch6 (stem volume).
- `_dispatch_cc()`'s KBD block now handles `cc==7` → `track.mixer_device.volume.value = val/127.0`; the Stems block adds a CC1..N volume branch using the same `val/127.0` formula.
- No Cmd+M mapping needed anymore for KBD or Stem volume, mute, or solo — all fully automatic now.

**Known remaining gap: CLICK/GUIDE (Master aux row, ch5) still rely entirely on Cmd+M** — there is no `rig_config.json` binding for these two aux tracks (unlike KBD/stems/loopers, which all have named config lists), so the Remote Script has no way to resolve which Ableton track they even are. Closing this gap needs either (a) David's real Ableton track names for Click and Guide so a small new config section can be added, or (b) leaving them Cmd+M-mapped as-is if that's preferred. Not yet resolved — see Pending tasks.

## Bidirectional volume feedback + Click/Guide scaffolding — shipped 2026-07-01 (commit `1674e86`)

After the volume-fader fix above, David asked: "make sure bi directional communication is intact if not implement it. If I move a fader in ableton the changes i make should reflect on LiveRig." Checked — it wasn't. KBD/Stem/FX-Return volume control had zero feedback path; only color/name/macro-value/looper-state had listeners.

- New outbound SysEx: `FB_KBD_VOLUME` (0x52), `FB_STEM_VOLUME` (0x53), `FB_RETURN_VOLUME` (0x54), `FB_AUX_VOLUME` (0x55) — each backed by a `mixer_device.volume` value listener + emitter in `LiveRig.py`, exactly mirroring the existing color/name listener pattern (`_rebind_*_volume_listeners`/`_unbind_*`/`_emit_*_volume`/`_emit_all_*_volumes`). Wired into `_connect_listeners` (init), `disconnect` (unbind), `_on_tracks_changed` (rebind + re-emit when track devices change), and `_emit_full_state` (fresh snapshot on iPad reconnect).
- `live_rig_3_controller.html`: `buildMaster()`/`buildStems()` fader elements now have stable ids (`master-fdr-{track,fill,val}-{cat}-{idx}` where cat is `kbd`/`aux`/`return`; `stem-fdr-{track,fill,val}-{idx}`) so feedback can target the right DOM node. New fb 0x52-0x55 handler + shared `updateChannelVolumeFeedback(cat, idx, v14)` — uses the same touch-guard pattern as `applyKbdMacros()` (`track.dataset.touching`) so a live Ableton-side change never yanks the fader out from under an active finger-drag.
- **Also scaffolded full Click/Guide ("aux") automation while in there**, since it's the same class of gap: new `rig_config.json` `"aux"` section (trackName-bound, no positional fallback — same pattern as stems/loopers), `_resolve_aux_track_index`, direct CC dispatch (CC20/21=volume, 24/25=mute, 28/29=solo on ch5/index4), and the same volume-feedback-listener treatment. **Deliberately opt-in**: `build_midi_map()` only registers ch5's CCs if `rig_config.json` actually has a non-empty `"aux"` list (`self._aux_count > 0`) — with no aux config (today's state), these CCs are left completely alone so David's existing Cmd+M mapping for Click/Guide keeps working unchanged. As soon as real track names are added to `rig_config.json`'s new `aux` section, this activates automatically on next Remote Script reload — no further code changes needed.
- **Still needed from David: the real Ableton track names for Click and Guide.** Once provided, add to `rig_config.json`:
  ```json
  "aux": [
    {"id": "click", "label": "CLICK", "trackName": "<real Click track name>"},
    {"id": "guide", "label": "GUIDE", "trackName": "<real Guide track name>"}
  ]
  ```
- Verified all 4 feedback categories + the touch-guard + a missing-element safety case via jsdom/Node unit tests before shipping.
- **Not yet confirmed live by David** — next step is reloading the Remote Script and testing: move a KBD/Stem/Return fader in Ableton with the mouse, confirm the iPad fader follows without needing to touch it.

## Sandbox git-lock friction — resolved 2026-07-01 via `allow_cowork_file_delete`

The recurring "stale git lock" problem (see dedicated section below) used to require David to manually run `rm -f .git/*.lock` from his own Terminal after nearly every commit. This is now self-service: calling the `mcp__cowork__allow_cowork_file_delete` tool (granting delete permission for the `liverig` folder) lets Claude clear these lock files itself mid-session without asking David to leave the chat. This grant is per-folder and may need to be re-requested if working in a different connected folder, but for `~/Desktop/liverig/` specifically it should not need to be asked for again.

## Pending tasks (carried forward, not yet superseded)

~~Remove the temporary `_dump_looper_params(0)` diagnostic call~~ — done, call site and now the dead method body are both gone (`4e971c3`).
~~Open/merge PR for `feature/extensions-sdk-setup` → `main`~~ — done, merged as `c4c9430`.
~~Restructure controller HTML markup to support >4 keyboards~~ — done, see section above (`4e971c3`).
~~Build "blue hand" mode~~ — done, see section above (`727a6c7`). Not yet confirmed live by David.
~~Delete stray `claude/keen-mestorf-aedfa5` branch/worktree~~ — done, confirmed gone (David ran the cleanup from his own Terminal; `.git/worktrees/` no longer even exists).
~~Fix Stems (tab 2) fader sizing, remove Master LOOPS fader, replace Clips play-icon emoji, show real clip names on Clips tiles~~ — done, see "Four UI fixes" section above (`4954ee8`).
~~Rebuild Clips page for native Ableton clip control + accurate playing/triggered/recording state~~ — done, see "Clips page: native Live API control" section above (`867820e`). Not yet confirmed live by David.
~~Fix Master/Stems volume faders not controlling Ableton~~ — done, see dedicated section above (`9a5233d`). Not yet confirmed live by David.
~~Add bidirectional volume feedback (KBD/Stems/FX Returns)~~ — done, see dedicated section above (`1674e86`). Not yet confirmed live by David.
~~Add packaged (.ablx) build for LiveRig Setup Tool~~ — done, see Extensions SDK section above (`881a29e`). Not yet confirmed installed/working by David — actually confirmed 2026-07-01: David dragged it in and the right-click menu worked.
~~Add ONBOARDING.md full setup walkthrough~~ — done. Answered David's template-session-vs-runtime-binding question directly, then documented all 5 phases plus an honest gap list.
~~Auto-deploy Remote Script from LiveRig.app launcher + build_dmg.sh~~ — done, see "Remote Script deployment gap" section above. **Not yet run/confirmed by David** — he needs to run `scripts/build_dmg.sh` once (macOS-only tools, can't be done from a Claude session) to re-sign the app and produce the installer.

0. **David needs to run `scripts/build_dmg.sh` once** — re-signs `/Applications/LiveRig.app` (fixes the signature invalidated by today's launcher-script edit) and builds `dist/LiveRig-Installer.dmg`. Top item; until this runs, the app bundle's signature is stale and may cause the same TCC/Gatekeeper friction hit before (see 2026-06-29 entry below).
1. **Get the real Ableton track names for Click and Guide from David**, then add the `rig_config.json` "aux" section (template in the section above) — this is the one remaining blocker to fully automating Click/Guide the same way KBD/Stems/Returns just were. Everything else (Python resolution, dispatch, feedback) is already built and just waiting on this.
2. **Confirm the volume-fader fix + new bidirectional feedback live** — move KBD/Stem/Return faders both on the iPad and with the mouse in Ableton, confirm both directions track correctly without fighting an active drag.
3. **Confirm the new native Clips page live in Ableton** — tap clips on the iPad, confirm real launch/stop/stop-all and correct blink→play→(optionally recording) visual transitions.
4. Confirm Blue Hand mode live in an actual Ableton session (test HAND toggle + track-click re-targeting on the iPad).
5. Decide whether to delete superseded `SESSION_BACKUP.md` from repo root (archive copy already safe at `~/Documents/LiveRig_Archive/SESSION_BACKUP_2026-05-01.md`). Still present at repo root as of 2026-07-01.
6. Multi-computer routing UI (Option A architecture) — when needed.
7. Extensions SDK setup-tool modal (`liverig-setup-tool/`) has no field yet for per-keyboard `midiChannel` or for adding a 5th+ keyboard slot — currently requires hand-editing `rig_config.json` to actually use the new >4 keyboard support. Natural next step if David wants to provision a real 5th keyboard through the modal instead of by hand.
8. Cosmetic gap: KBD5+ live Ableton track-color changes (fb 0x44) don't repaint the dynamic `--kbd-c`-based elements (KBD1-4 use global `--k1..--k4` vars which already work). Low priority, control unaffected.
9. Remaining foolproof-ness gaps from ONBOARDING.md not yet tackled: silent fallback on a missing/bad `rig_config.json` (no user-facing warning), silent no-op on an unmatched stem/looper/aux track name (no visible "unbound" indicator on the iPad).
10. `liverig_bridge_wired.py` still carries a fully dead M4L/HTTP-JSON `live_state`/`handle_http()` mechanism (with a placeholder `"clips"` field) that nothing uses anymore now that Clips page data comes from the Remote Script — left in place, harmless, candidate for cleanup whenever convenient.

## Known sandbox quirk: stale git locks (2026-06-30)

The Claude session's filesystem bridge to `~/Desktop/liverig` sometimes can't unlink git's internal lock files (`index.lock`, `HEAD.lock`, `refs/remotes/origin/*.lock`) — commands fail with "Operation not permitted" instead of actually removing them, and even read-only commands like `git status` can leave one behind. When a git command from a Claude session fails with "Another git process seems to be running" / "Unable to create '.../index.lock'", the fix is for David to run, from his own Terminal (not through Claude):
```
cd ~/Desktop/liverig
rm -f .git/index.lock .git/HEAD.lock .git/refs/remotes/origin/main.lock
```
This is a sandbox-mount limitation, not repo corruption — David's local git is always fine underneath it. GitHub push access itself works fine once a PAT is configured as a git credential inside the session (done 2026-06-30, stored at `~/.git-credentials` inside the sandbox — separate from David's own Mac Keychain PAT).

## How to resume in a new chat

1. Read this file first — it's the live state, not `SESSION_BACKUP.md`.
0. **Whenever `LiveRig/LiveRig.py` changes, sync it to `~/Music/Ableton/User Library/Remote Scripts/LiveRig/LiveRig.py` before considering the work done** — see "Remote Script deployment gap" section near the top. This is separate from the git commit/push and separate from the LiveRig.app bundle sync; skipping it means David tests against stale code with zero error message, which is exactly what happened 2026-07-01 and cost significant back-and-forth diagnosing a "bug" that was actually just an undeployed fix.
2. The Master page is fully working as of 2026-07-01: 10 channels (KBD 1-4, CLICK/GUIDE, REV 1/REV 2/DLY 1/DLY 2 — LOOPS fader removed), mute/solo automatic via Remote Script. No open regressions.
3. >4 keyboard support shipped 2026-06-30 (`4e971c3`) — see dedicated section above. KBD_COUNT is dynamic now; adding a real 5th+ keyboard still means hand-editing `rig_config.json` until the setup-tool modal grows the field for it.
4. Blue Hand mode shipped 2026-06-30 (`727a6c7`) — see dedicated section above. Built and verified via jsdom, but **not yet confirmed live by David**.
5. The stray `claude/keen-mestorf-aedfa5` branch/worktree is gone (David cleaned it up from his own Terminal 2026-06-30).
6. Clips page rebuilt 2026-07-01 (`867820e`) for native Live API clip firing/stopping + accurate playing/triggered/recording state, replacing the old fake-MIDI-note approach — see dedicated section above. **Not yet confirmed live by David** — that's the top item in Pending tasks.
7. Continue from "Pending tasks" above — next up is confirming the new Clips control live, then Blue Hand, then the `SESSION_BACKUP.md` deletion decision.
8. Respect channel isolation and architectural decisions listed above. Note the reserved-channel set now also includes CH15 (Blue Hand) on top of CH5/6/7/10/16.
9. Don't reintroduce removed features (Record/Punch/Overdub on Setlist, STEMS nav button on Master, LOOPS fader on Master, etc.) without confirming with David first.
10. Use `~/Library/Preferences/Ableton/Live 12.4.2/Log.txt` for Ableton log checks — not the old 12.3.8 folder.
11. **Deployment pipeline**: edit `~/Desktop/liverig/` source → copy HTML/bridge to bundle Resources → restart LiveRig app. Check `/private/tmp/liverig_controller_served.html` timestamp to confirm the menubar script re-generated the served file. Use Chrome extension's `read_console_messages` to verify no JS errors before telling David to check the iPad. `LiveRig.py` (Remote Script) is a THIRD, separate deployment target — `~/Music/Ableton/User Library/Remote Scripts/LiveRig/LiveRig.py` — that this session now has direct write access to; sync it there too (see item 0 above), then a Live restart or Control Surface dropdown toggle (not an app relaunch) is what actually reloads it.
12. **Git lock friction is resolved** — no need to ask David to clear lock files from Terminal anymore; call `mcp__cowork__allow_cowork_file_delete` for the `liverig` folder if a commit hits a stale-lock error.
13. **Two more folders now connected as of 2026-07-01**: `~/Library/Preferences/Ableton` (parent, for checking which Live version folder is actually newest — there are two active installs, stable Suite `12.4.2` for the main rig and Beta `12.4.5bN` for Extensions SDK work, don't mix up their Log.txt files) and `~/Music/Ableton/User Library/Remote Scripts` (see item 0).
