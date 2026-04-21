# LiveRig — iPad MIDI Controller for Ableton Live

Control Ableton Live from your iPad over a USB cable. No WiFi, no latency, no extra apps.

---

## What's in the box

| File | What it does |
|------|-------------|
| `live_rig_3_controller.html` | The iPad controller — open in Safari |
| `liverig_bridge_wired.py` | Runs on your Mac, translates WebSocket → MIDI |
| `LiveRig_Wired_Start.sh` | Double-click launcher — handles everything |

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

## Troubleshooting

**Dot stays red / can't connect**
- Is the launcher dialog open on your Mac? If you closed it, the bridge stopped.
- Did the iPad show "Trust This Computer"? Unplug, replug, tap Trust.
- Check the IP — tap the status bar to re-enter it.

**No MIDI reaching Ableton**
- Ableton Preferences → MIDI → confirm "LiveRig Bridge" Input has Track + Remote enabled.
- Try the **PANIC** button on the controller to send All Notes Off.

**No feedback from Ableton to iPad (BPM, transport, bar counter not updating)**
- Ableton Preferences → MIDI → confirm "LiveRig Bridge" **Output** also has Track + Remote enabled.
- You need a Max for Live device in your set to send the feedback CCs. See [M4L Setup](#m4l-setup) below.

**"Python 3 not found" even after install**
- Open Terminal and run: `python3 --version`
- If that works but the script doesn't, try: `chmod +x LiveRig_Wired_Start.sh` then run again.

**Bridge crashes on start**
- Check the log: open Terminal → `cat /tmp/liverig_bridge.log`

---

## M4L Setup (optional — for Ableton feedback)

To get BPM, transport state, and bar counter on the iPad, add a Max for Live MIDI device to your set that sends:

| CC | Channel | Value | Meaning |
|----|---------|-------|---------|
| CC 14 | 1 | 0–127 (maps to 40–240 BPM) | Current BPM |
| CC 15 | 1 | 127=Playing, 64=Rec, 0=Stopped | Transport state |
| CC 16 | 1 | 0–127 | Current bar |
| CC 17 | 1 | Time signature numerator | e.g. 4 for 4/4 |

Send to MIDI output: **LiveRig Bridge**

---

## MIDI Map reference

### Master page
| Control | Channel | CC / Note |
|---------|---------|-----------|
| K1 buttons B1–B4 | CH 1 | CC 20–23 |
| K2 buttons B1–B4 | CH 2 | CC 20–23 |
| K3 buttons B1–B4 | CH 3 | CC 20–23 |
| K4 buttons B1–B4 | CH 4 | CC 20–23 |
| Volume faders | CH 1–4 | CC 7 |

### Pads page
| Control | Channel | Notes |
|---------|---------|-------|
| Pads 1–16 | CH 10 | C2–D#3 (36–51) |
| FX Reverb | CH 1 | CC 70 |
| FX Delay | CH 1 | CC 71 |
| FX Chorus | CH 1 | CC 72 |
| FX Distort | CH 1 | CC 73 |

### Looper page
| Control | Channel | CC |
|---------|---------|-----|
| Loop 1 Rec/Play | CH 1 | CC 80 (127=rec, 64=play) |
| Loop 2 Rec/Play | CH 2 | CC 81 |
| Loop 3 Rec/Play | CH 3 | CC 82 |
| Loop 4 Rec/Play | CH 4 | CC 83 |
| Loop 1 Stop | CH 1 | CC 84 |
| Loop 2 Stop | CH 2 | CC 85 |
| Loop 3 Stop | CH 3 | CC 86 |
| Loop 4 Stop | CH 4 | CC 87 |
| Tempo fader | CH 1 | CC 14 |
| BPM nudge up | CH 1 | CC 90 |
| BPM nudge down | CH 1 | CC 91 |

### Keyboard pages (Kbd 1–4)
| Control | Channel | CC |
|---------|---------|-----|
| Buttons B1–B16 | CH 1–4 | CC 20–35 |
| CC sliders 1–8 | CH 1–4 | CC 10–17 |

### Patches page
Program Change sent on CH 1–4 simultaneously (PC 0–7 for Songs 1–8).

---

## Requirements

- **Mac** running macOS 12 or later
- **iPad** with Safari (any modern iPad works)
- **USB cable** (Lightning or USB-C to USB-A/C depending on your Mac)
- **Ableton Live** 10 or later (Suite for M4L feedback; Standard works for basic control)
- Python 3.8+ *(installed automatically by the launcher)*
