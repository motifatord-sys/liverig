# Building the tester template Live Set (David — one-time, in Ableton)

Goal: a small Live Set whose track names match the shipped tester config
(`tester/rig_config.default.json`, seeded into the app) so your friend's LiveRig binds to everything the
moment he opens it — using **only stock Ableton instruments** (he won't have
Omnisphere or your other plugins).

Save the finished set as **`tester/LiveRig-Template.als`** in the repo (or hand
me the path); `build_dmg.sh` will bundle it onto the DMG.

## Tracks — exact names (case doesn't matter, spelling does)

Create these tracks, named exactly. Order doesn't matter (binding is by name).

**Keyboard tracks (MIDI):**
- **`MAIN KEYS`** — MIDI track. Put a stock synth (e.g. **Wavetable** or **Analog**) inside an **Instrument Rack** (select the instrument → right-click → Group). The Instrument Rack matters: LiveRig's 8 KBD faders bind to the Rack's 8 **Macro** knobs, and fader feedback only works for Rack-wrapped devices. Map a few macros to something audible (filter cutoff, reverb, etc.) so moving faders is obviously doing something.
- **`TOP KEYS`** — same idea, another stock synth in an Instrument Rack.

**Stem tracks (any track type — these only need volume / mute / solo):**
- **`DRUMS`** — a Drum Rack with a stock kit, or an audio track with a drum loop.
- **`BASS`** — stock instrument (e.g. Operator/Bass) or audio.
- **`KEYS`** — stock instrument or audio.
- **`VOX`** — audio track (drop in any vocal/audio clip) or an instrument.
- **`CLICK`** — a metronome-style click. Simplest: a MIDI track with a stock drum hit on each beat, or just an audio click loop. (It's here so your friend can mix/mute the click like a stem.)
- **`GUIDE`** — a "guide/cues" track — any instrument or audio track.

**Looper track:**
- **`Loop 1`** — an **audio** track with Ableton's **Looper** device on it (Audio Effects → Looper). LiveRig drives its rec/play/stop/undo.

**Marker track (drives the Transport section strip):**
- **`MARKERS`** — a **MIDI** track. In **Arrangement View**, place named dummy MIDI clips end-to-end, each spanning one song section: e.g. `INTRO` (bars 1–4), `VERSE` (5–12), `CHORUS` (13–20), `OUTRO` (21–24). The clip **names** become the section labels; each clip should **span** its section.

## Arrangement setup (so the fun stuff demos)

- Put a little content in the Arrangement on the stem/keys tracks (a few clips) so there's audio to mix and something plays when he hits Play.
- Add **locators** for the Setlist page: in Arrangement, drop a locator at the start of each "song" and name it with the `Song:` prefix — e.g. `Song: Demo One`, `Song: Demo Two`. LiveRig lists `Song:`-prefixed locators on the Setlist page (text after `Song:` is the title). Two or three is plenty for a demo.
- He performs by playing the **Arrangement** timeline (that's what drives the bar/beat display and the section strip).

## Save

- File → Save As → **`LiveRig-Template.als`**, put it at `~/Desktop/liverig/tester/LiveRig-Template.als`.
- Keep it lightweight — a couple of short clips per track is enough to show LiveRig working. The point is to demonstrate binding, faders, transport, sections, and the setlist, not to be a finished song.

Once it's saved, tell me and I'll fold it into the DMG build.
