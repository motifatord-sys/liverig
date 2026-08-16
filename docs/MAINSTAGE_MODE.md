# MainStage Mode — setup guide

LiveRig's MSTG tab controls Apple MainStage over the same "LiveRig Bridge"
virtual MIDI port Ableton uses — and gets **two-way sync** using MainStage's
own motorized-fader feedback mechanism ("Send Value to"), since MainStage has
no scripting API. One-time setup below; after that it just works, including
running MainStage and Ableton side by side (everything lives on its own MIDI
channel, default **CH 14**).

## What the page sends

| Control        | MIDI (on `mainstage.midiChannel`, default 14) |
|----------------|-----------------------------------------------|
| Patch buttons  | Program Change 0..patchCount-1                |
| Faders         | CC 1..faderCount                              |
| Toggles        | CC 20..(19+buttonCount), value 127/0          |

Config lives in `rig_config.json` under `"mainstage"` (enabled, midiChannel,
patchCount, faderCount, buttonCount). The MSTG tab hides itself entirely when
`enabled` is false.

## One-time MainStage setup

### 0. Port
MainStage listens to all MIDI inputs by default — "LiveRig Bridge" is already
live. LiveRig.app must be running (it owns the port).

### 1. Patch switching (one-way, no feedback available)
For each patch in your concert: select the patch → Patch Inspector →
**Attributes** → set **Program Change** to the number matching the LiveRig
button (button 1 = PC 0, button 2 = PC 1, …). Tapping a patch button on the
iPad now selects that MainStage patch.
> MainStage cannot report the current patch back, so the purple highlight on
> the iPad reflects the last button *you* tapped there.

### 2. Faders — the two-way part
For each of the (default 8) faders, in **Layout mode**:
1. Add/select a knob or fader screen control.
2. In the Screen Control Inspector, click the **Learn** button, then move the
   matching fader on the iPad's MSTG page — MainStage learns `CH14 CC1` (etc.).
3. Still in the inspector, set **"Send Value to"** → choose the
   **LiveRig Bridge** output. This is the motorized-fader feedback feature:
   whenever the screen control's value changes — you turn it with a mouse, a
   mapped parameter moves it, or a **patch change snaps it to saved values** —
   MainStage sends the CC back out, and the iPad fader follows.
4. In Edit mode, map the screen control to whatever parameter you want, per
   patch, as usual.

Repeat for the toggle buttons (CC 20+). Buttons reflect incoming 127/0 as
on/off.

### 3. Avoiding surprises
- **Channel isolation:** everything here is on CH 14. Ableton's LiveRig
  channels (1-4 KBD, 6 stems, 7 FX, 10 pads, 15 Blue Hand, 16 transport) are
  untouched, so both apps can run simultaneously. If MainStage should ignore
  the Ableton-facing channels, set your concert/patch MIDI input filters
  accordingly (or just don't Learn anything from those channels).
- **Echo loops:** safe by design — an echo of a value the iPad just sent is a
  visual no-op, and incoming feedback never fights an active finger-drag.
- **Patch names** on the iPad are set with the RENAME button (arm → tap a
  patch). They're stored per-iPad for now.

## Troubleshooting
- Fader doesn't move on the iPad when you change patches in MainStage →
  the screen control's **"Send Value to"** isn't set to LiveRig Bridge.
- Nothing reaches MainStage → check LiveRig.app is running (menu bar 🎹) and
  the MSTG tab is visible (config `enabled: true`, page reloaded fresh).
- Wrong controls move → another device is also sending on CH 14; change
  `mainstage.midiChannel` (then relaunch LiveRig.app + reload the iPad and
  re-Learn in MainStage).
