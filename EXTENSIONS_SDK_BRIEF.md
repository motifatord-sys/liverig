# LiveRig Setup Tool — Ableton Extensions SDK Brief

> Written for Claude Code, working on branch `feature/extensions-sdk-setup`. Grounded in the actual SDK docs at `~/Documents/extensions-sdk-1.0.0-beta.0/` (read directly, not guessed) as of 2026-06-26.

## What this branch is building

A small Ableton Extension — a TypeScript/Node.js plugin that runs inside Live's Extension host — that gives David a UI *inside Live* for configuring `rig_config.json`, instead of hand-editing JSON. It reads real track names from the current Live Set so he can pick which tracks map to KBD1–4 and which are stem tracks, instead of typing blind.

**This tool only ever produces a config file. It must never touch `LiveRig.py` or the Remote Script** — that's `refactor/rig-config`'s territory (see `BRANCHING_STRATEGY.md`).

## Critical constraint: the SDK cannot write to ~/Desktop/liverig/

This is the single most important fact from the docs (`docs/essentials/concepts/6-resources-and-filesystem.html`):

> Your extension should not access arbitrary paths like the user's Documents, Downloads, or Desktop folders.
> A stricter OS-level sandbox will be introduced in the future... Any workaround that accesses files outside the allowed paths is unsupported and will likely break.

Extensions may only read/write:
- `context.environment.storageDirectory` — persistent, survives across sessions (this is where the tool's working copy of the config lives)
- `context.environment.tempDirectory` — scratch space, may be cleared

So the extension **cannot directly save `rig_config.json` into `~/Desktop/liverig/`.** Plan around this rather than fighting it:

1. The extension reads/writes its working config at `context.environment.storageDirectory/rig_config.json`.
2. A separate, already-trusted process moves it into place. The cleanest option: extend `LiveRig_Wired_Start.sh`'s existing Python heredoc (which already consolidates all Desktop-folder I/O into one trusted interpreter call) to also check the extension's known storage directory and copy a newer config over if found. This keeps "only one binary touches the Desktop folder" intact — the lesson learned earlier this project from the repeated macOS permission-prompt bug.
3. Alternative fallback if (2) is awkward: the modal dialog shows the final JSON in a read-only textarea with a "Copy to Clipboard" button, and David pastes it into `rig_config.json` himself. Less elegant, but zero filesystem risk and works today without coordinating two codebases.

Don't try to shell out or use raw Node `fs` to write outside the allowed directories "because it currently works" — the docs explicitly call this an unsupported workaround that will break when stricter sandboxing ships.

## What the SDK is and isn't for (confirmed from docs/getting-started/1-introduction.html)

Extensions run as **Node.js processes alongside Live**, with full npm access, and they're good for:
- Reading/writing tracks, clips, devices, scenes (batch operations on the Live Set)
- Custom UI via modal-dialog webviews (HTML/CSS/JS)
- File import/audio rendering through `context.resources`

Explicitly **not** designed for, per the docs:
- Real-time audio processing
- MIDI routing or real-time MIDI manipulation
- Drawing into Live's native UI
- Background/persistent extensions (must be running with Live open; no daemon mode)
- **Control Surface integration**

That last point matters a lot for this project: the Extensions SDK is **not** a path to replacing the Python Remote Script or the WebSocket MIDI bridge. It's purely a config-time helper. Don't scope-creep it into doing anything live/real-time — that's what `LiveRig.py` and the bridge are for.

## Project scaffolding (docs/getting-started/2-quick-start.html)

```
mkdir ~/Projects/liverig-setup-tool   # or wherever Claude Code is working
cd ~/Projects/liverig-setup-tool
npx file:/path/to/extracted/ableton-create-extension-1.0.0-beta.0.tgz
```

The creator prompts for: extension name, author, the Live install to target, and whether you need a UI (say yes — we need the modal dialog form). It scaffolds:

```
manifest.json        # name, author, entry, version, minimumApiVersion
build.ts
package.json         # scripts: start, build, package
src/extension.ts
vendor/*.tgz          # SDK + CLI packages
```

Before `npm start` will work, enable **Preferences → Extensions → Developer Mode** in the Live Beta build. `npm start` builds and hot-loads the extension into the running Live instance.

## Core API shape (grounded examples)

**Activation:**
```ts
import { initialize, type ActivationContext } from "@ableton-extensions/sdk";

export function activate(activation: ActivationContext) {
  const context = initialize(activation, "1.0.0");
  // context.application, context.commands, context.ui, context.resources, context.environment
}
```

**Reading the current Live Set's tracks** (for the KBD/stem picker):
```ts
const song = context.application.song;
const tracks = song.tracks; // Track<Version>[]
tracks.forEach(t => console.log(t.name));
```
`Song` also exposes `scenes`, `returnTracks`, `mainTrack`, `cuePoints` — likely useful later for reading song/locator structure, not needed for the initial config tool.

**Commands + triggering the tool:** Commands are registered in `activate` and tied to context menu scopes (`AudioTrack`, `MidiTrack`, `Scene`, etc. — see `docs/essentials/interface/1-context-menu-items.html` for the full scope list). There is no generic "Song" or toolbar-level scope confirmed in the docs read so far — worth checking `docs/essentials/interface/1-context-menu-items.html` in full and the Examples folder again once you're in the editor, since the practical trigger point (e.g. right-click an audio/MIDI track → "Configure LiveRig") will probably need to hang off a track scope rather than a global menu item.

**The UI itself — modal dialog webview** (`docs/essentials/interface/2-user-interface-with-webviews.html`):
```ts
import modalInterface from "./interface.html"; // bundler inlines this as text — needs esbuild .html-as-text config, see Bundling docs

const result = await context.ui.showModalDialog(
  `data:text/html,${encodeURIComponent(modalInterface)}`,
  640, 480
);
const data = JSON.parse(result);
```
The HTML side must postMessage back through `window.webkit.messageHandlers.live.postMessage({ method: "close_and_send", params: [JSON.stringify(result)] })` (macOS) or the WebView2 equivalent on Windows — there's a documented boilerplate `<script>` block to copy verbatim, included in full in the webviews doc.

**Persisting the working config:**
```ts
import { promises as fs } from "fs";
import path from "path";

const configPath = path.join(context.environment.storageDirectory, "rig_config.json");
await fs.writeFile(configPath, JSON.stringify(rigConfig, null, 2));
```

**Object references are Handles, not live objects** — when a command receives a clicked-on object, it arrives as a numeric `Handle`; resolve it with `context.getObjectFromHandle(handle, Track)` (or whatever class is expected for that scope) before reading `.name` etc.

## Relevant example projects to study (already on disk, full source)

- `examples/modal-dialog/` — the clearest template: registers a command, shows a webview form, parses the JSON result, applies it. Closest match to what this tool needs structurally.
- `examples/progress-dialog/` — if config generation/validation ends up slow enough to need a spinner.
- `examples/arrangementselection/` — shows reading track/selection state and creating objects from it; useful pattern reference even though our tool doesn't touch clips.

## Suggested first milestone

1. Scaffold the extension per Quick Start.
2. Get a "Hello World" modal dialog showing — confirms Developer Mode + build pipeline work end to end.
3. Wire up reading `song.tracks` and rendering the track list inside the modal's HTML form.
4. Build the form fields against `rig_config.schema.json` (already on `main`/`refactor/rig-config` in this repo — use it as the literal contract, don't redefine field names independently).
5. Write the assembled config to `context.environment.storageDirectory/rig_config.json`.
6. Solve the "get it onto the Desktop folder" handoff — either the launcher-script copy step or the clipboard fallback described above. Decide with David before building both.

## Schema contract reminder

Per `BRANCHING_STRATEGY.md`: this branch may only ever *write* configs conforming to `rig_config.schema.json`. It must never change the schema unilaterally — a schema change is a PR against `main`, reviewed in whichever session didn't propose it.
