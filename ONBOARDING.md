# LiveRig — Full Setup & Operation Guide

> Written 2026-07-01 in response to David asking for the complete install-to-operation walkthrough, and specifically: does a new Live Set need a template with tracks pre-bound, or can the Extensions SDK tool bind things at runtime? Short answer to that question is right below; the full phase-by-phase walkthrough follows, ending with an honest list of what is NOT yet foolproof.

## The core question: template session vs. runtime binding

**Both, and they're not in tension — here's the model:**

`rig_config.json` binds Ableton **track names** (strings like `"MAIN KEYS"`, `"DRUMS"`, `"Loop 1"`) to LiveRig UI elements (KBD1-4 faders, stem columns, looper slots). It does not care about a Live Set's file path or its track *order* — only whether a track with that exact name (case-insensitive) exists when `LiveRig.py` loads.

That means:

- **You need exactly one canonical Live Set** (a "template") whose tracks are named to match `rig_config.json` — this already exists conceptually; the current `rig_config.json`'s `rigName: "Main Live Rig"` and its track names (`MAIN KEYS`, `TOP KEYS`, `KEYS L`, `KEYS R`, `DRUMS`, `PERC/LOOP`, `BASS`, `GTR`, `AUX`, `FX`, `VOCALS`, `LEAD VOCALS`, `Loop 1`-`Loop 4`) describe exactly that rig.
- **Every new gig or song should be a duplicate of that template**, not a fresh Live Set built from scratch. As long as the duplicate keeps the same track names, `rig_config.json` never needs to change and nothing needs to be re-bound.
- **The Extensions SDK tool (right-click → "Configure LiveRig…") is for the one-time setup of a new template, or for re-binding when the track structure genuinely changes** (renaming a track, adding a 5th keyboard, moving a stem to a different track). It reads whichever Live Set is open *right now* and writes a `rig_config.json` snapshot of that moment — it's not something that needs to run every session.

So: don't hand a fresh end user a blank Live Set and expect the config tool to save them per-session. Give them (or build once, yourself) a template Live Set with the right tracks, run the Setup Tool once against it, and from then on duplicating that template is what keeps everything bound correctly.

## Phase 1 — One-time machine setup

Do this once per computer that will run LiveRig.

1. **Install Ableton Live 12 Suite** (the stable release) — this is the DAW used for actual performance.
2. **Install Ableton Live 12 Suite Beta 12.4.5+** *only if you'll use the Extensions SDK config tool* — Extensions require the beta build specifically; they are not available in the stable Suite, Standard, Intro, or Lite. This is a completely separate app install from #1, with its own preferences folder.
3. **Get the LiveRig repo onto the machine** at `~/Desktop/liverig/` (git clone `motifatord-sys/liverig`, or copy the folder).
4. **Install LiveRig.app** (drag `dist/LiveRig-Installer.dmg`'s contents to `/Applications`, or drag the raw `.app` if not using the DMG yet) — this bundles the MIDI bridge, the menubar helper, the iPad-facing HTML frontend, **and now the Ableton Remote Script too**. As of 2026-07-01, the first launch (and every launch after that where the bundled script changed) automatically copies `LiveRig.py` + `__init__.py` into `~/Music/Ableton/User Library/Remote Scripts/LiveRig/` for you — no manual copy step anymore. A dialog pops up telling you to restart Ableton (or toggle the Control Surface dropdown) whenever it actually deployed a change, since that reload step still can't be automated away.
5. **(For distributing to a new machine)** Run `scripts/build_dmg.sh` on a Mac that has the current `LiveRig.app` installed — it re-signs the app and produces `dist/LiveRig-Installer.dmg`, a proper drag-to-Applications installer with a Read Me. Needs to be re-run whenever the app bundle's contents change.
6. **One-time Ableton MIDI setup** (per machine, in the stable Suite): Settings → Link, Tempo & MIDI → find an empty Control Surface row → Control Surface = `LiveRig`, Input = `LiveRig Bridge`, Output = `LiveRig Bridge`, both with Track and Remote switched on.
7. **Install the packaged Setup Tool extension** *(optional, only needed if configuring via the modal UI)*: in Live 12 Beta, Preferences → Extensions → Developer Mode off → drag in `liverig-setup-tool/dist/liverig-setup-tool.ablx` (run `npm run package` in that folder first if it doesn't exist yet).

## Phase 2 — Build or confirm the template Live Set

1. Build (or confirm you already have) a Live Set with the exact track roles LiveRig expects: 4+ keyboard tracks (each with an Instrument Rack or plugin), your stem tracks, dedicated looper tracks (each with Ableton's native Looper device on it), and the standard FX return tracks (Reverb/Delay — these are automatic, not something you create by hand).
2. Save this as your canonical template.
3. Going forward, **duplicate this file** for new gigs/songs rather than starting blank.

## Phase 3 — Generate or update `rig_config.json`

Only needed once per template, or whenever track structure changes.

**Option A — Extensions SDK tool** (Live 12 Beta):
1. Open the template Live Set in Live 12 Beta.
2. Right-click any audio or MIDI track → "Configure LiveRig…"
3. Fill in KBD1-4 track bindings, bank size, stems (label/track/default volume), max patches. Save.
4. The config is written to the extension's own storage folder (sandboxed — Extensions can't write directly to `~/Desktop`). `LiveRig_Wired_Start.sh`'s launcher script compares mtimes and copies the newer config over to `~/Desktop/liverig/rig_config.json` on the next LiveRig.app launch.

**Option B — hand-edit `rig_config.json` directly.** Currently **required** for two things the modal doesn't expose yet: loopers and aux (Click/Guide) bindings. See the gap list below.

## Phase 4 — Launch, day of show

1. Open the gig's Live Set (a duplicate of the template) in the **stable Suite**, not the Beta.
2. Launch LiveRig.app — starts the bridge, the menubar helper, and serves the iPad HTML.
3. Confirm the Control Surface row from Phase 1 step 6 is still set (this lives in Ableton's global preferences, not per-project, so it should already be there).
4. On the iPad, open Safari to the LiveRig URL (shown by the menubar app).
5. Confirm connection: status bar shows live BPM/transport, Master page faders reflect the current Live Set's actual track state.

## Phase 5 — Ongoing operation

Once connected, everything is live and bidirectional: transport, scene launching and stopping (native Live API, not fake MIDI notes), Clips page with real clip names and playing/triggered/recording state, Blue Hand mode (KBD page follows whatever track is selected in Live), KBD/Stem/Return volume faders (now bidirectional as of today), mute/solo, and Looper record/play/stop/undo/quantization. A full state resync happens automatically whenever the iPad reconnects or the Remote Script restarts.

## What is NOT yet fully foolproof — honest gap list

1. ~~Remote Script deployment is entirely manual~~ — **closed 2026-07-01.** `LiveRig.app`'s launcher script now auto-deploys `LiveRig.py`/`__init__.py` into the Remote Scripts folder on every launch (only notifying when content actually changed). Still needs `scripts/build_dmg.sh` run once on David's Mac to re-sign the app (invalidated by the launcher-script edit) and produce the installer — `codesign`/`hdiutil` are macOS-only, unavailable in a Claude sandbox session.
2. **The Extensions SDK Setup Tool doesn't have fields for loopers or aux (Click/Guide) yet** — only KBD1-4 and stems. Those two categories still require hand-editing `rig_config.json`'s `loopers[]` and `aux[]` arrays directly.
3. **Silent fallback on a missing/bad config.** If `rig_config.json` is absent or malformed, `LiveRig.py` falls back to a generic hardcoded 4×8 positional default with zero user-facing warning — a differently-ordered Live Set would get silently wrong bindings.
4. **Silent no-op on an unmatched track name.** Stems, loopers, and aux tracks have no positional fallback — if a track name in `rig_config.json` doesn't match anything in the Live Set, that channel just silently does nothing. It's logged to `Log.txt`, but nothing tells the user on the iPad that a fader is unbound versus just not being touched yet.
5. **One-time Ableton MIDI preferences setup (Phase 1 step 6) is manual** — there's no way for a Remote Script or Extension to configure Live's own MIDI preferences from the outside, so this will always require a human doing it once per machine.
6. **The full config-tool → sync → reload chain hasn't been verified end-to-end in one continuous test** — the modal writing a config, the launcher script picking it up, and `LiveRig.py` re-reading it after a restart have each been tested individually but not confirmed back-to-back in a single session today.

Closing any of these is real, scoped work — my instinct for what's next is #3 or #4 (some kind of visible "unbound" indicator instead of silent no-ops), since those are the ones a future you (or someone else running this rig) would hit with zero clue why something isn't working.
