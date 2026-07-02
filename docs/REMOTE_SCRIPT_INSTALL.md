# LiveRig Remote Script — Install & Usage

The LiveRig Remote Script is a Python control surface for Ableton Live 11/12 that gives you **true bidirectional feedback** for parameters, no polling, and selected-track awareness — without requiring a Max for Live device on a track.

It runs alongside (or instead of) the existing M4L device. Both can coexist; you don't have to remove anything.

## What it adds vs M4L-only

| Capability | M4L only | + Remote Script |
|------------|----------|-----------------|
| Native transport SysEx | ✅ | ✅ |
| Marker / scene navigation | ✅ | ✅ |
| Real-time parameter feedback (bidirectional Macros) | poll-based, ~2s lag | **listener-based, instant** |
| Selected-track awareness (blue-hand) | ❌ | ✅ |
| BPM / time / scenes / cues update | poll-based, ~3-5s lag | **instant** |
| Works without M4L device on any track | ❌ | ✅ |
| Audio thread cost | small (poll cycles) | **none** |

## Install

1. **Locate Live's Remote Scripts folder:**
   ```
   ~/Music/Ableton/User Library/Remote Scripts/
   ```
   If `Remote Scripts` doesn't exist, create it.

2. **Unzip `LiveRig_RemoteScript.zip` into that folder.** You should end up with:
   ```
   ~/Music/Ableton/User Library/Remote Scripts/
   └── LiveRig/
       ├── __init__.py
       └── LiveRig.py
   ```

3. **Restart Ableton Live** (or close and reopen it — Live only scans Remote Scripts on startup).

4. **Enable in Ableton:**
   - Live → Settings → Link, Tempo & MIDI
   - In the **Control Surface** section, find an empty row
   - Set **Control Surface** dropdown → `LiveRig`
   - Set **Input** dropdown → `LiveRig Bridge`
   - Set **Output** dropdown → `LiveRig Bridge`
   - You should see a brief on-screen message: "LiveRig connected"

5. **Confirm it's running** — Live's log file (`~/Library/Preferences/Ableton/Live <version>/Log.txt`) should contain:
   ```
   LiveRig Remote Script loaded.
   ```

## Verify

After connecting:
- Tap iPad **Play** — Ableton starts. (This already worked through M4L, but now it works through Remote Script too — both paths are active.)
- Move a Macro on an Instrument Rack on Track 1 with your mouse — the iPad's KBD1 fader should follow **immediately** (no 2-second lag).
- Rename a scene in Session view — within a few hundred ms the iPad's Clips page right column updates.
- Click on a different track in Ableton — the iPad knows which track is selected (visible in `m4l.selectedTrack` JS state — used for future "blue hand" features).

## Coexistence with M4L device

Both LiveRig paths can be active at once:

- **Remote Script handles**: transport, scene firing, cue/scene/track listeners, macro feedback, selected-track tracking
- **M4L device handles**: per-track utilities, file-based state JSON (legacy compat)

If both are active, the iPad receives **two streams of state updates**. That's fine — they're additive. You can either:
- Keep both for redundancy
- Remove the M4L device from your tracks and rely solely on the Remote Script

I recommend keeping both for now until the Remote Script is field-tested in your live use.

## Troubleshooting

**"LiveRig" doesn't appear in the Control Surface dropdown**
The folder isn't in the right place or Live didn't restart. Verify the path is exactly `~/Music/Ableton/User Library/Remote Scripts/LiveRig/__init__.py`.

**Connected but no feedback on iPad**
Check Live's log file for any `LiveRig` errors. The most common issue is the input/output ports — both must be set to `LiveRig Bridge` in the Control Surface row.

**Want to disable temporarily without uninstalling**
In Settings → MIDI → Control Surface, set the LiveRig row's Control Surface dropdown to `None`.

**Editing the script**
Each time you edit `LiveRig.py`, restart Live (or toggle the Control Surface to `None` and back to `LiveRig`).

## What's not in this initial version

These are coming next:
- Full mixer control (mute/solo/volume listeners + iPad updates)
- "Blue hand" mode (KBD pages auto-bind to selected track's first 8 device params)
- CC mapping with `map_midi_cc_with_feedback_map` (built-in Live MIDI mapping with automatic feedback — the cleanest way to map iPad faders to ANY parameter, with feedback for free)
- Per-track macro listeners for tracks beyond KBD1-4
