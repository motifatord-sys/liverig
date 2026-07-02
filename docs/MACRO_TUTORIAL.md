# LiveRig — Macro-Based Bidirectional Control Setup

This tutorial sets up your four keyboard tracks (KBD1–KBD4) so the LiveRig faders display **the actual current value** of plugin parameters — even when you change them with your mouse, with the plugin's own UI, or with another controller.

## Prerequisites

- You're using Ableton Live Suite (Macros require this — Standard works only with limitations)
- LiveRig Bridge running and the M4L device dropped on a track in your set

## How it works

Ableton Live's **Instrument Rack** (and Audio/MIDI Effect Racks) expose 8 **Macro Knobs** that can drive any parameter inside the rack. Macros are first-class objects in the Live API — LiveRig reads their current value every ~2 seconds and updates your iPad faders to match.

When **you** move a LiveRig fader, it sends MIDI CC → that's MIDI-mapped to a Macro → the Macro updates → ALL bound parameters update. When **anything else** moves the Macro (mouse, plugin UI, another controller), LiveRig sees the new value and the iPad fader follows.

## Setup steps (do once per keyboard track)

You'll repeat this for each of your four keyboard tracks. We'll use **Track 1** (KBD1) as the example.

### 1. Wrap your instrument in a Rack

1. In Ableton Session view, select **Track 1**
2. Open the device chain at the bottom (your Omnisphere instance is there)
3. Right-click on **Omnisphere** → **Group** *(or press Cmd+G)*
4. Omnisphere is now wrapped in an **Instrument Rack** — you'll see "Macro 1, Macro 2, …, Macro 8" appear above the device chain

### 2. Show the Macros panel

- Click the small **chain/macro toggle** on the left edge of the Rack header
- The 8 Macro knobs appear

### 3. Map plugin parameters to Macros

For each parameter you want LiveRig to control:

1. Right-click on the **plugin parameter** you want to expose (in Omnisphere's UI or in Ableton's parameter view)
2. Choose **Map to Macro 1** *(or Macro 2, etc.)*
3. The Macro now controls that parameter

Map any 8 parameters this way — for example:
- Macro 1 → Filter Cutoff
- Macro 2 → Resonance
- Macro 3 → Attack
- Macro 4 → Release
- Macro 5 → Reverb Send
- Macro 6 → Delay Send
- Macro 7 → Pitch Bend Range
- Macro 8 → Master Volume

### 4. Rename the Macros

Right-click each Macro → **Rename** → give it a descriptive name like "CUTOFF" or "REVERB". These names will appear on the LiveRig fader labels automatically.

### 5. Map LiveRig faders to the Macros

This is the standard MIDI Map procedure:

1. In Ableton, press **Cmd+M** to enter MIDI Map mode (mappable areas highlight)
2. Click **Macro 1** in the Rack
3. Move **Fader 1 (CC10)** on the iPad's KBD1 page
4. Ableton binds them — you'll see `Ch.1 CC.10` in the MIDI Mappings list
5. Click **Macro 2** → move **Fader 2 (CC11)** on iPad
6. Repeat for all 8 macros (CC10–17)
7. Press **Cmd+M** to exit MIDI Map mode

### 6. Set Takeover Mode (recommended)

To prevent jumps when LiveRig and your mouse both touch the same Macro:

1. Open Ableton **Preferences → Link/Tempo/MIDI**
2. Find **MIDI Takeover Mode**
3. Set to **Pickup** *(or Value Scaling)*
4. Now LiveRig has to "catch up" to the current value before it takes over — no parameter jumping

### 7. Repeat for KBD2, KBD3, KBD4

Same procedure on Tracks 2, 3, 4. LiveRig automatically maps:
- KBD1 → Track 1's first Instrument Rack
- KBD2 → Track 2's first Instrument Rack
- KBD3 → Track 3's first Instrument Rack
- KBD4 → Track 4's first Instrument Rack

## Save it forever

After setup, save your Live Set as the default template:

1. **File → Save Live Set as Default**

Now every new Live Set starts with all four KBD racks mapped — no re-doing this work.

## What you'll see on iPad

After you finish:
- Each fader on KBD1 shows the **actual Macro name** (CUTOFF, REVERB, etc.) instead of "CC10"
- Faders update live when you change parameters anywhere — plugin UI, mouse drag, keyboard automation
- Tap a fader on iPad → Macro moves → all bound parameters move

## Troubleshooting

**Faders still labeled "CC10"–"CC17"**
The track has no Instrument Rack on it. Group the device with Cmd+G.

**Fader values don't match parameter values**
The Macro range is 0–127 by default. If your Macro is set to a non-default range (right-click → Range), LiveRig normalizes to 0–127 for display.

**Plugin UI moves but iPad fader doesn't**
Make sure your iPad fader is mapped to the **Macro**, not directly to the plugin parameter. Direct CC mappings to plugin parameters bypass the Live API and won't echo back.

**iPad fader is fighting with my mouse**
Enable Takeover Mode (Preferences → MIDI → Takeover → Pickup).

**Lag when changing parameters**
Macros refresh every ~2 seconds. The iPad fader catches up, then stays in sync. This delay is intentional — keeps Ableton CPU low.

## Buttons (CC20-35)

The 16 toggle buttons (CC20–35) on each KBD page still send one-way only. To get bidirectional buttons, you'd need to map them to On/Off device parameters via Macros (a Macro can drive a Device On/Off if you toggle the Macro between 0 and 127). We can add that later if needed.
