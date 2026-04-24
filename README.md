# LiveRig — iPad MIDI Controller for Ableton Live

Control Ableton Live from your iPad over a USB cable. No WiFi, no latency, no extra apps.

---

## What's in the box

| File | What it does |
|------|-------------|
| `live_rig_3_controller.html` | The iPad controller — open in Safari |
| `liverig_bridge_wired.py` | Runs on your Mac, translates WebSocket ↔ MIDI |
| `LiveRig_Wired_Start.sh` | Double-click launcher — handles everything |
| `LiveRig_Bridge.maxpat` | Max for Live device — sends transport/state back to iPad |
| `liverig_send.js` | JavaScript helper loaded by the M4L device |

---

## Mac setup (one time only)

### Step 1 — Download

Click the green **Code** button on this page → **Download ZIP** → unzip it anywhere (Desktop works fine).

### Step 2 — Run the launcher

Double-click **`LiveRig_Wired_Start.sh`**

> **First time only:** macOS may say *"cannot be opened because it is from an unidentified developer"*.
> Right-click the file → **Open** → **Open** to allow it.

The script will:
- Install Python 3 automatically if you don't have it *(takes ~3 min, one-time)*
- Install the two required packages (`python-rtmidi`, `websockets`)
- Start the bridge and copy your iPad IP to the clipboard

### Step 3 — Enable in Ableton

Open Ableton → **Preferences** → **MIDI** tab:

```
Input:  LiveRig Bridge   →   Track ✓   Remote ✓
Output: LiveRig Bridge   →   Track ✓   Remote ✓
```

> You only need to do this once. Ableton remembers it.

### Step 4 — Load the Max for Live device (optional but recommended)

This gives the iPad real-time BPM, bar, beat, and transport state from Ableton.

1. Copy `liverig_send.js` to `~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/`
2. Open `LiveRig_Bridge.maxpat` in Max, save as `LiveRig_Bridge.amxd`
3. Drop the `.amxd` onto any MIDI track in your Live set

---

## iPad setup (one time only)

### Step 1 — Trust your Mac

Plug your iPad into your Mac with a USB cable.
If the iPad shows **"Trust This Computer?"** — tap **Trust**.

### Step 2 — Open the controller

On your Mac, find `live_rig_3_controller.html` → **AirDrop it to your iPad**
(or email it to yourself, save to Files, open with Safari).

In Safari on iPad: tap the **Share** button → **Add to Home Screen**
This makes it feel like a native app.

### Step 3 — Connect

1. Open the LiveRig app on your iPad
2. The status bar at the top says **"Tap to set Mac IP…"** — tap it
3. Paste the IP address (it was copied to your clipboard when you ran the launcher)
4. The dot turns **green** — you're connected ✅

---

## Every day use

```
1. Plug iPad into Mac via USB
2. Double-click LiveRig_Wired_Start.sh on your Mac
3. Open the LiveRig app on your iPad
4. Play
```

The launcher dialog stays open while the bridge runs.
Click **Stop Bridge** when you're done.

---

## How to MIDI-map LiveRig to Ableton

LiveRig sends standard MIDI CC, Note, and Program Change messages. Map them using Ableton's MIDI Map Mode:

1. In Ableton, press **Cmd+M** to enter MIDI Map Mode (mappable areas highlight)
2. Click the parameter or button you want to control in Ableton
3. Tap the corresponding control on your iPad
4. Ableton binds them automatically
5. Press **Cmd+M** again to exit

Save your Live set as a template (`File → Save Live Set as Default`) so mappings persist across new projects.

---

## Full MIDI Map

All messages are conflict-free. Buttons that appear on multiple pages (Master + KBD) intentionally share the same CC since they represent the same physical control.

### Transport page (CH 1)
| Control | CC | Notes |
|---------|-----|-------|
| Play | 116 | value 127 |
| Stop | 117 | value 127 |
| Record | 118 | value 127 |
| Overdub | 119 | toggle 0/127 |
| Metronome | 112 | toggle 0/127 |
| Loop | 113 | toggle 0/127 |
| Punch In | 114 | toggle 0/127 |
| Undo | 115 | value 127 |
| Redo | 111 | value 127 |
| Tempo Bend Down | 108 | hold to fire |
| Tempo Bend Up | 107 | hold to fire |
| BPM fader | 14 | 0–127 maps to 40–240 BPM |

### Looper page (CH 1)
| Control | CC |
|---------|-----|
| Loop 1 Rec/Play | 80 (127=rec, 64=play) |
| Loop 2 Rec/Play | 81 |
| Loop 3 Rec/Play | 82 |
| Loop 4 Rec/Play | 83 |
| Loop 1–4 Stop | 84–87 |
| Tap Tempo | 89 |
| BPM Nudge Down | 90 |
| BPM Nudge Up | 91 |

### Master page
| Control | Channel | CC |
|---------|---------|-----|
| K1 buttons B1–B4 | CH 1 | CC 20–23 |
| K2 buttons B1–B4 | CH 2 | CC 20–23 |
| K3 buttons B1–B4 | CH 3 | CC 20–23 |
| K4 buttons B1–B4 | CH 4 | CC 20–23 |
| Volume faders K1–K4 | CH 1–4 | CC 7 |

### Keyboard pages (Kbd 1–4)
| Control | Channel | CC |
|---------|---------|-----|
| Buttons B1–B16 | CH 1–4 | CC 20–35 |
| CC sliders 1–8 | CH 1–4 | CC 10–17 |

### Pads page
| Control | Channel | Notes / CC |
|---------|---------|-----------|
| Pads 1–16 | CH 10 | Notes 36–51 (C2–D#3) |
| FX 1 (Reverb) | CH 1 | CC 70 |
| FX 2 (Delay) | CH 1 | CC 71 |
| FX 3 (Chorus) | CH 1 | CC 72 |
| FX 4 (Distort) | CH 1 | CC 73 |

### Clip Launcher page (CH 1)
| Control | Note / CC |
|---------|-----------|
| Clip launch (8×8 grid) | Notes 48–111 (row-major) |
| Track Stop 1–8 | CC 52–59 |
| Scene Launch 1–8 | CC 60–67 |
| Stop All Clips | CC 68 |

### Patches page
Program Change sent on CH 1–4 simultaneously when a song is tapped.

| Song | PC |
|------|-----|
| Song 1 | PC 0 |
| Song 2 | PC 1 |
| ... | ... |
| Song 8 | PC 7 |

### SysEx (locator navigation — requires M4L device)
| Command | Bytes |
|---------|-------|
| Jump to locator N | `F0 7D 30 N F7` |
| Next locator | `F0 7D 31 00 F7` |
| Previous locator | `F0 7D 32 00 F7` |

---

## Inbound feedback (Ableton → iPad)

When the M4L device is loaded, Ableton sends state back to the iPad via JSON over WebSocket (no MIDI traffic used). The iPad displays:

- Live BPM
- Transport state (playing / stopped / recording)
- Current bar and beat
- Time signature
- Song name
- Locator list and current locator

---

## Troubleshooting

**Dot stays red / can't connect**
- Is the launcher dialog open on your Mac? If you closed it, the bridge stopped.
- Did the iPad show "Trust This Computer"? Unplug, replug, tap Trust.
- Check the IP — tap the status bar to re-enter it.

**No MIDI reaching Ableton**
- Ableton Preferences → MIDI → confirm "LiveRig Bridge" Input has Track + Remote enabled.
- Try the **PANIC** button on the controller to send All Notes Off.

**No feedback from Ableton to iPad (BPM, transport, bar counter not updating)**
- Confirm the M4L device is dropped on a MIDI track in your Live set.
- Check the Max console (Window → Max Console) for errors.
- The device writes `/tmp/liverig_state.json` — if missing, check Max's file search path includes the folder containing `liverig_send.js`.

---

## Requirements

- **Mac** running macOS 12 or later
- **iPad** with Safari (any modern iPad works)
- **USB cable** (Lightning or USB-C to USB-A/C depending on your Mac)
- **Ableton Live** 10 or later (Suite required for M4L feedback; Standard works for basic control)
- Python 3.8+ *(installed automatically by the launcher)*
