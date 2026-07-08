import { promises as fs } from "fs";
import path from "path";
import {
  initialize,
  AudioTrack,
  MidiTrack,
  Track,
  type ActivationContext,
  type Handle,
} from "@ableton-extensions/sdk";

import modalInterface from "./interface.html";

interface RigKeyboard {
  id: string;
  label: string;
  bankSize: number;
  defaultTrackBinding: string | null;
  buttonCount: number;
  faderCount: number;
  faderRange: { min: number; max: number };
  /** 1-indexed MIDI channel; omit to auto-assign (see LiveRig.py). */
  midiChannel?: number;
}

interface RigLooper {
  id: string;
  label: string;
  trackName: string | null;
}

interface RigStem {
  id: string;
  label: string;
  trackName: string | null;
  defaultVolume: number;
}

interface RigConfig {
  version: string;
  rigName?: string;
  keyboards: RigKeyboard[];
  patches: {
    maxPatches: number;
    restoreAnimation?: {
      durationMs: number;
      easing: string;
      stepIntervalMs: number;
      stepCount: number;
    };
    captureScope?: string[];
  };
  stems?: RigStem[];
  loopers?: RigLooper[];
  /** Track whose named Arrangement clips define song sections. */
  markerTrack?: string | null;
  /** OSC lighting cues -- edited by hand for now, passed through untouched. */
  lighting?: unknown;
  listeners?: {
    useSchedulePollForSongTime: boolean;
    songTimePollHz: number;
    wrapListenersInTryExcept: boolean;
  };
}

const DEFAULT_CONFIG: RigConfig = {
  version: "1.0",
  rigName: "Main Live Rig",
  keyboards: [
    { id: "kbd1", label: "KBD 1", bankSize: 8, defaultTrackBinding: null, buttonCount: 16, faderCount: 8, faderRange: { min: 0, max: 127 } },
    { id: "kbd2", label: "KBD 2", bankSize: 8, defaultTrackBinding: null, buttonCount: 16, faderCount: 8, faderRange: { min: 0, max: 127 } },
    { id: "kbd3", label: "KBD 3", bankSize: 8, defaultTrackBinding: null, buttonCount: 16, faderCount: 8, faderRange: { min: 0, max: 127 } },
    { id: "kbd4", label: "KBD 4", bankSize: 8, defaultTrackBinding: null, buttonCount: 16, faderCount: 8, faderRange: { min: 0, max: 127 } },
  ],
  patches: {
    maxPatches: 8,
    restoreAnimation: { durationMs: 500, easing: "ease-out-cubic", stepIntervalMs: 20, stepCount: 25 },
    captureScope: ["kbd1", "kbd2", "kbd3", "kbd4"],
  },
  stems: [],
  loopers: [],
  markerTrack: null,
  listeners: {
    useSchedulePollForSongTime: true,
    songTimePollHz: 10,
    wrapListenersInTryExcept: true,
  },
};

export function activate(activation: ActivationContext) {
  const context = initialize(activation, "1.0.0");

  context.commands.registerCommand("liverig.configure", (_args: unknown) =>
    (async () => {
      const storageDir = context.environment.storageDirectory ?? "";
      const configPath = path.join(storageDir, "rig_config.json");

      let existingConfig: RigConfig = DEFAULT_CONFIG;
      try {
        const raw = await fs.readFile(configPath, "utf-8");
        existingConfig = JSON.parse(raw);
      } catch {
        // no existing config — use defaults
      }

      const song = context.application.song;
      const trackNames: string[] = [];
      for (const track of song.tracks) {
        if (track instanceof AudioTrack || track instanceof MidiTrack) {
          trackNames.push(track.name);
        }
      }

      const payload = encodeURIComponent(JSON.stringify({ config: existingConfig, trackNames }));
      const encodedHtml = encodeURIComponent(
        (modalInterface as string).replace("__INITIAL_DATA__", payload)
      );

      const result = await context.ui.showModalDialog(
        `data:text/html,${encodedHtml}`,
        780,
        600
      );

      if (!result) return;

      const updatedConfig: RigConfig = JSON.parse(result);
      updatedConfig.version = "1.0";

      await fs.mkdir(storageDir, { recursive: true });
      await fs.writeFile(configPath, JSON.stringify(updatedConfig, null, 2), "utf-8");

      console.log(`[LiveRig Setup] Config saved to ${configPath}`);
    })()
  );

  // ── Marker/locator sync (2026-07-06) ──────────────────────────────────────
  // David maintains two parallel navigation systems by hand: Ableton locators
  // (cue points -- what the Transport prev/next buttons and the Setlist page
  // jump to) and the MARKERS track's named arrangement clips (what feeds the
  // Transport section strip). These two commands sync them in one click, in
  // either direction. Both are strictly NON-DESTRUCTIVE: they only CREATE
  // missing things, never rename, move, or delete existing ones (per this
  // project's nothing-gets-deleted policy) -- so both are safe to re-run
  // any time (idempotent: a second run creates nothing).
  const EPS = 1e-3; // beat-position tolerance when matching times

  const escHtml = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  async function showSummary(title: string, lines: string[]): Promise<void> {
    const html =
      `<!doctype html><html><body style="font-family:-apple-system,Helvetica,sans-serif;` +
      `background:#1a1a22;color:#eee;padding:18px 22px">` +
      `<h3 style="margin:0 0 12px">${escHtml(title)}</h3>` +
      `<pre style="font-size:13px;line-height:1.5;white-space:pre-wrap;margin:0 0 16px">` +
      lines.map(escHtml).join("\n") +
      `</pre><button style="padding:6px 18px;font-size:13px" onclick="done()">Close</button>` +
      `<script>function done(){var m={method:'close_and_send',params:['ok']};` +
      `if(window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.live)` +
      `{window.webkit.messageHandlers.live.postMessage(m);}` +
      `else if(window.chrome&&window.chrome.webview){window.chrome.webview.postMessage(m);}}` +
      `</scr` + `ipt></body></html>`;
    await context.ui.showModalDialog(
      `data:text/html,${encodeURIComponent(html)}`, 460, 380);
  }

  // Locator names may carry the setlist convention prefix "Song: <name>"
  // (song boundary). As section clips we want the bare name.
  const stripSongPrefix = (name: string) => {
    const t = name.trim();
    return /^song:/i.test(t) ? t.slice(5).trim() : t;
  };

  // Right-click the MARKERS track -> creates one locator at the start of
  // each named section clip that doesn't already have one there.
  context.commands.registerCommand("liverig.markersToLocators", (...args: unknown[]) =>
    (async () => {
      const track = context.getObjectFromHandle(args[0] as Handle, MidiTrack);
      const song = context.application.song;
      const clips = [...track.arrangementClips]
        .filter((c) => (c.name || "").trim() !== "")
        .sort((a, b) => a.startTime - b.startTime);
      if (clips.length === 0) {
        await showSummary("Markers → Locators",
          [`No named arrangement clips on "${track.name}".`,
           "This command reads the marker track's section clips."]);
        return;
      }
      const existing = song.cuePoints.map((c) => c.time);
      const toCreate = clips.filter(
        (c) => !existing.some((t) => Math.abs(t - c.startTime) < EPS));
      if (toCreate.length > 0) {
        // One user-facing undo step for the whole batch. withinTransaction
        // requires a synchronous callback; returning Promise.all of the
        // async creations is the documented pattern.
        await context.ui.withinProgressDialog(
          `Creating ${toCreate.length} locator(s)…`, { progress: 0 },
          async () => {
            await context.withinTransaction(() =>
              Promise.all(toCreate.map(async (c) => {
                const cp = await song.createCuePoint(c.startTime);
                cp.name = c.name.trim();
              })));
          });
      }
      await showSummary("Markers → Locators", [
        `Marker track: "${track.name}" (${clips.length} named clip(s))`,
        `Created: ${toCreate.length} locator(s)`,
        `Already had a locator at that position: ${clips.length - toCreate.length}`,
        "", "Existing locators are never renamed, moved, or deleted.",
      ]);
      console.log(`[LiveRig Sync] markers->locators: +${toCreate.length}`);
    })().catch((e) => console.error("[LiveRig Sync] markers->locators failed:", e))
  );

  // Right-click the (empty or partial) MARKERS track -> creates one named
  // MIDI clip per locator, spanning to the next locator. Spans that would
  // overlap an existing clip on that track are skipped, never overwritten.
  context.commands.registerCommand("liverig.locatorsToMarkers", (...args: unknown[]) =>
    (async () => {
      const track = context.getObjectFromHandle(args[0] as Handle, MidiTrack);
      const song = context.application.song;
      const cues = [...song.cuePoints].sort((a, b) => a.time - b.time);
      if (cues.length === 0) {
        await showSummary("Locators → Marker Clips",
          ["This Set has no locators (cue points).",
           "Add locators in the Arrangement first, or use Markers → Locators."]);
        return;
      }
      // A locator has no length; each span runs to the next locator. The
      // last one runs to the end of the arrangement material (max clip end
      // across ALL tracks), with a 16-beat floor so it's never zero-length.
      let songEnd = 0;
      for (const t of song.tracks)
        for (const c of t.arrangementClips)
          if (c.endTime > songEnd) songEnd = c.endTime;
      const existing = track.arrangementClips.map(
        (c) => ({ s: c.startTime, e: c.endTime }));
      const plans: { start: number; dur: number; name: string }[] = [];
      let skippedOverlap = 0;
      for (let i = 0; i < cues.length; i++) {
        const start = cues[i].time;
        const end = i + 1 < cues.length
          ? cues[i + 1].time
          : Math.max(songEnd, start + 16);
        if (end - start < EPS) continue; // co-located locators
        if (existing.some((x) => x.s < end - EPS && x.e > start + EPS)) {
          skippedOverlap++;
          continue;
        }
        plans.push({ start, dur: end - start,
                     name: stripSongPrefix(cues[i].name) || `Section ${i + 1}` });
      }
      if (plans.length > 0) {
        await context.ui.withinProgressDialog(
          `Creating ${plans.length} marker clip(s)…`, { progress: 0 },
          async (update) => {
            // Sequential on purpose: concurrent createMidiClip calls on ONE
            // track for adjacent ranges is exactly the kind of engine-side
            // race we don't need to find out about mid-show.
            for (let i = 0; i < plans.length; i++) {
              const p = plans[i];
              const clip = await track.createMidiClip(p.start, p.dur);
              clip.name = p.name;
              await update(`Creating marker clips… ${i + 1}/${plans.length}`,
                           Math.round(((i + 1) / plans.length) * 100));
            }
          });
      }
      await showSummary("Locators → Marker Clips", [
        `Target track: "${track.name}"`,
        `Locators in Set: ${cues.length}`,
        `Clips created: ${plans.length}`,
        `Skipped (would overlap an existing clip): ${skippedOverlap}`,
        "", "Existing clips are never moved, renamed, or overwritten.",
        `Reminder: rig_config.json markerTrack is "MARKERS" — the section`,
        "strip reads whichever track that names.",
      ]);
      console.log(`[LiveRig Sync] locators->markers: +${plans.length}, skipped ${skippedOverlap}`);
    })().catch((e) => console.error("[LiveRig Sync] locators->markers failed:", e))
  );

  context.ui.registerContextMenuAction(
    "AudioTrack",
    "Configure LiveRig...",
    "liverig.configure"
  );

  context.ui.registerContextMenuAction(
    "MidiTrack",
    "Configure LiveRig...",
    "liverig.configure"
  );

  context.ui.registerContextMenuAction(
    "MidiTrack",
    "LiveRig: Create Locators from Marker Clips",
    "liverig.markersToLocators"
  );

  context.ui.registerContextMenuAction(
    "MidiTrack",
    "LiveRig: Create Marker Clips from Locators",
    "liverig.locatorsToMarkers"
  );
}
