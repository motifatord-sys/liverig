# LiveRig — Tester Quick Start

Thanks for test-driving LiveRig! It's a touch control surface for Ableton Live
that runs in a browser (an iPad is the intended feel, but any device with a web
browser on the same WiFi works — even this Mac). This should take about 10
minutes to get running.

## What you'll need

- A **Mac** running **Ableton Live 12**.
- A device with a **web browser on the same WiFi** as the Mac — an iPad is
  ideal, but an iPhone, another laptop, or even this same Mac is fine for
  trying it out.

## 1. Install

1. Open **LiveRig-Installer.dmg**.
2. Drag **LiveRig** onto the **Applications** folder shortcut.

## 2. First launch (important — one-time macOS step)

Because this is a test build (not from the App Store), macOS will block it the
first time. To get past it:

- In **Applications**, **right-click LiveRig → Open**, then click **Open** in
  the dialog. (Just double-clicking won't give you the "Open" option — you have
  to right-click the first time.)
- If macOS says LiveRig is **"damaged"**, open **Terminal** and paste this once,
  then try right-click → Open again:
  ```
  xattr -cr /Applications/LiveRig.app
  ```

**The first launch takes 3–5 minutes** — LiveRig sets up its own components and
may ask for your Mac password. This only happens once. When it's ready you'll
see a small **🎹 keyboard icon in your menu bar** (top-right of the screen).

## 3. Tell Ableton about LiveRig (one-time)

1. In Ableton: **Settings → Link, Tempo & MIDI** (Live menu → Settings, then the
   "Link, Tempo & MIDI" tab).
2. Under **MIDI → Control Surface**, pick an empty row and set:
   - **Control Surface:** `LiveRig`
   - **Input:** `LiveRig Bridge`
   - **Output:** `LiveRig Bridge`
3. Below, in the MIDI Ports list, make sure **Track** and **Remote** are **On**
   for both the Input and Output rows named `LiveRig Bridge`.
4. Quit and reopen Ableton once so it loads LiveRig.

## 4. Open the demo Live Set

Open **LiveRig-Template.als** (included with this installer). It has tracks
already named to match LiveRig, so everything connects automatically.

## 5. Open the controller

- Click the **🎹 menu bar icon** — it shows LiveRig's address (something like
  `http://10.0.0.x:8080/...`).
- On your **iPad/phone/laptop**, open that address in the browser (same WiFi).
- Or, to try it right on this Mac: menu bar icon → **"Preview in Browser
  (this Mac)."**

You should see live BPM/transport and the faders reflecting the Live Set.

## 6. Give it a spin

- Hit **Play** on the Transport page — watch the bar/beat and the section strip
  (Intro / Verse / Chorus…) follow along as the song plays.
- Move the **MAIN KEYS / TOP KEYS** faders — they drive those instruments in
  Ableton (and follow along if you move them in Ableton too).
- Mix the **stems** (Drums/Bass/Keys/Vox), mute/solo, ride **Click** and
  **Guide**.
- Try the **Looper**, the **Patches** page (Program Change presets), and the
  **Setlist** page (it lists the `Song:` markers from the set).

## 7. Send David feedback

Anything that felt confusing, broke, or that you loved — jot it down and send it
back. Especially useful: what was unclear during setup, anything that didn't
respond, and what you'd want it to do that it doesn't.

Thanks! 🎹
