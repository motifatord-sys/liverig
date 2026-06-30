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
}

interface RigStem {
  id: string;
  label: string;
  trackName: string;
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
}
