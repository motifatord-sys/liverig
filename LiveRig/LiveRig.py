"""LiveRig — Ableton Live Remote Script.

Provides:
  * SysEx-driven transport control (Play/Stop/Rec/Tap/Loop/Punch/Overdub/Undo/Redo)
  * Marker navigation (prev/next cue, jump-by-index)
  * Scene firing (by index)
  * Listener-driven feedback over the same MIDI port:
      - BPM, song time, transport state
      - Cue point list (names + times)
      - Scene names
      - Selected track name + index
      - Macro values for tracks 0-3 (KBD1-4) — emitted as CC for bidirectional sync
  * Optional MIDI CC mapping to instrument rack macros with native feedback,
    so the iPad fader follows ANY change to the Macro (mouse, plugin, automation).

The bridge sends SysEx in the form: F0 7D <code> <value> F7
The script emits status updates as a stream of SysEx feedback messages over the
configured output port. The bridge translates those to JSON for the iPad.

Status SysEx format (script -> bridge):
  F0 7D 60 <type> <data...> F7
where <type>:
  0x00 = transport state    | data: 0=stopped, 1=playing, 2=recording
  0x01 = bpm                | data: high7 low7 (BPM*100, 14-bit)
  0x02 = song_time          | data: 4 7-bit bytes (beats fixed-point ms*1)
  0x03 = song_len           | data: 4 7-bit bytes
  0x10 = cue add/update     | data: index, name length, name bytes, time4
  0x11 = cue remove         | data: index
  0x12 = cue list begin     | data: count
  0x13 = cue list end
  0x20 = scene add/update   | data: index, name length, name bytes
  0x22 = scene list begin   | data: count
  0x23 = scene list end
  0x30 = selected track     | data: index, name length, name bytes
  0x40 = macro value        | data: track_idx, macro_idx, value14_high, value14_low,
                                     name length, name bytes
  0x44 = kbd track color    | data: kbd_idx, r14_high, r14_low, g14_high, g14_low,
                                     b14_high, b14_low (each channel 0-255 in 14-bit)
  0x45 = kbd track name     | data: kbd_idx, name length, name bytes
  0x46 = stem track color   | data: stem_idx, r14_high, r14_low, g14_high, g14_low,
                                     b14_high, b14_low (each channel 0-255 in 14-bit)
  0x47 = stem track name    | data: stem_idx, name length, name bytes
  0x48 = loop state         | data: loop_idx, state (0=stop, 1=record, 2=play)

Direct CC handling (via build_midi_map — no CMD+M needed for these):
  KBD    CC1=mute, CC2=solo   → KBD track mute/solo (resolves via defaultTrackBinding).
         Each keyboard's MIDI channel comes from rig_config.json's "midiChannel"
         (1-indexed) or, if absent, auto-assigned to the next channel not already
         claimed by ch5 (aux)/ch6 (stems)/ch7 (FX returns)/ch10 (pads)/ch16
         (transport) — KBD1-4 default to ch1-4, same as before.
  ch6    CC N+1..2N = mute, 2N+1..3N = solo  → Stem tracks (N = stem count)
  ch7    CC1-4=vol, CC5-8=mute, CC9-12=solo  → Return tracks A-D (Reverb1/2, Delay1/2)

Looper (dedicated loop tracks, native Ableton Looper device control):
inbound codes 0x4B-0x4E carry a loop index (0-3, per rig_config.json's
"loopers" array) as the value byte, and drive the bound track's Looper
device "State" parameter directly via the Live Object Model -- not
Ableton's MIDI Map Mode, which can't cleanly express the Looper's
single combined State enum as discrete button presses.
  0x4B = loop rec    | value: loop_idx
  0x4C = loop play   | value: loop_idx
  0x4D = loop stop    | value: loop_idx
  0x4E = loop undo   | value: loop_idx (pulses the device's Undo param)
"""
from __future__ import absolute_import, print_function, unicode_literals

import json
import os

import Live
from _Framework.ControlSurface import ControlSurface

# ── rig_config.json loading ───────────────────────────────────────────────────
# Generalizes the old hardcoded "4 keyboards / 8-param banks" assumption.
# Falls back to those exact defaults if no config file is found or it's
# malformed, so an absent/broken config never breaks the script.
_DEFAULT_RIG_CONFIG = {
    "keyboards": [
        {"id": "kbd1", "label": "KBD 1", "bankSize": 8, "midiChannel": 1},
        {"id": "kbd2", "label": "KBD 2", "bankSize": 8, "midiChannel": 2},
        {"id": "kbd3", "label": "KBD 3", "bankSize": 8, "midiChannel": 3},
        {"id": "kbd4", "label": "KBD 4", "bankSize": 8, "midiChannel": 4},
    ]
}

# Checked in order; first one found wins. Covers both "script reads the repo
# copy directly" (dev) and "script reads a copy placed next to it" (installed).
_CONFIG_SEARCH_PATHS = [
    os.path.expanduser("~/Desktop/liverig/rig_config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "rig_config.json"),
]


def _load_rig_config(log=None):
    """Load rig_config.json from the first path that exists and parses cleanly.
    Returns _DEFAULT_RIG_CONFIG (a copy of the 4x8 layout) on any failure.
    """
    for path in _CONFIG_SEARCH_PATHS:
        try:
            if not os.path.isfile(path):
                continue
            with open(path, "r") as f:
                cfg = json.load(f)
            keyboards = cfg.get("keyboards")
            if not keyboards:
                raise ValueError("rig_config.json has no 'keyboards' array")
            if log:
                log("rig_config loaded from %s (%d keyboards)" % (path, len(keyboards)))
            return cfg
        except Exception as e:
            if log:
                log("rig_config load failed at %s: %s" % (path, e))
    if log:
        log("rig_config not found in any search path; using built-in 4x8 default")
    return _DEFAULT_RIG_CONFIG


# ── KBD MIDI channel assignment (2026-06-30, >4 keyboard support) ───────────
# KBD1-4 originally assumed MIDI ch1-4 (index 0-3) with no other option.
# Channels already claimed elsewhere (0-indexed): 4=CH5 aux (Click/Guide/
# Loops), 5=CH6 stems, 6=CH7 FX returns, 9=CH10 pads, 15=CH16 transport.
# Keyboards beyond the first 4 get the next free channel in that order
# unless rig_config.json specifies an explicit 1-indexed "midiChannel".
# Mirrors kbdDefaultChannel()/kbdChannel() in live_rig_3_controller.html --
# keep both in sync if the reserved set ever changes.
_RESERVED_KBD_CHANNELS_0IDX = (4, 5, 6, 9, 15)


def _default_kbd_channel_0idx(ti):
    count = 0
    for ch in range(16):
        if ch in _RESERVED_KBD_CHANNELS_0IDX:
            continue
        if count == ti:
            return ch
        count += 1
    return ti  # unreachable with <=11 keyboards given today's reserved set


def _kbd_channels_from_config(keyboards):
    """Returns a list of 0-indexed MIDI channels, one per keyboard, honoring
    an explicit 1-indexed "midiChannel" in rig_config.json when present."""
    channels = []
    for ti, kbd in enumerate(keyboards):
        configured = kbd.get("midiChannel")
        if isinstance(configured, int) and 1 <= configured <= 16:
            channels.append(configured - 1)
        else:
            channels.append(_default_kbd_channel_0idx(ti))
    return channels


# ── SysEx codes (incoming, from bridge to script) ────────────────────────────
SX_LOCATOR_JUMP    = 0x30
SX_LOCATOR_NEXT    = 0x31
SX_LOCATOR_PREV    = 0x32
SX_SCENE_FIRE      = 0x33
SX_PLAY            = 0x40
SX_STOP            = 0x41
SX_RECORD          = 0x42
SX_OVERDUB         = 0x43
SX_METRO           = 0x44
SX_LOOP            = 0x45
SX_PUNCH_IN        = 0x46
SX_TAP_TEMPO       = 0x47
SX_UNDO            = 0x48
SX_REDO            = 0x49
SX_REQUEST_FULL_STATE = 0x4A   # bridge asks script to re-emit all state
SX_LOOP_REC        = 0x4B   # value: loop_idx
SX_LOOP_PLAY       = 0x4C   # value: loop_idx
SX_LOOP_STOP       = 0x4D   # value: loop_idx
SX_LOOP_UNDO       = 0x4E   # value: loop_idx
SX_LOOP_QUANT      = 0x4F   # value: (loop_idx<<4)|quant_idx

# ── SysEx codes (outgoing, script to bridge) ─────────────────────────────────
SX_FB_PREFIX       = 0x60
FB_TRANSPORT       = 0x00
FB_BPM             = 0x01
FB_SONG_TIME       = 0x02
FB_SONG_LEN        = 0x03
FB_CUE_UPDATE      = 0x10
FB_CUE_LIST_BEGIN  = 0x12
FB_CUE_LIST_END    = 0x13
FB_SCENE_UPDATE    = 0x20
FB_SCENE_LIST_BEGIN = 0x22
FB_SCENE_LIST_END  = 0x23
FB_SELECTED_TRACK  = 0x30
FB_MACRO_VALUE     = 0x40
FB_KBD_COLOR       = 0x44
FB_KBD_NAME        = 0x45
FB_STEM_COLOR      = 0x46
FB_STEM_NAME       = 0x47
FB_LOOP_STATE      = 0x48
FB_LOOP_QUANT      = 0x49   # data: loop_idx, quant_idx

LIVERIG_MFG_ID     = 0x7D


class LiveRig(ControlSurface):
    """Top-level Remote Script class. Live instantiates this once."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._suppress_send_midi = False
        self._suggested_input_port = "LiveRig Bridge"
        self._suggested_output_port = "LiveRig Bridge"

        rig_config = _load_rig_config(log=self.log_message)
        self._kbd_count = len(rig_config["keyboards"])
        self._bank_sizes = [kbd.get("bankSize", 8) for kbd in rig_config["keyboards"]]
        # defaultTrackBinding: track name (str) or index (int) or None/unbound.
        # Resolved to an actual track index at bind-time via _resolve_kbd_track_index,
        # since the Live Set's track order can differ from KBD slot order.
        self._track_bindings = [kbd.get("defaultTrackBinding") for kbd in rig_config["keyboards"]]
        # 0-indexed MIDI channel per keyboard slot (see _kbd_channels_from_config
        # above) -- replaces the old hardcoded "channel index == KBD slot" (0-3)
        # assumption so >4 keyboards can each get a free channel.
        self._kbd_channels = _kbd_channels_from_config(rig_config["keyboards"])
        self._kbd_channel_to_index = {ch: ti for ti, ch in enumerate(self._kbd_channels)}

        # Stems: named tracks (e.g. backing-track stems) bound by trackName,
        # independent of the KBD1-4 slots. Color/name feedback only -- volume/
        # mute/solo control is plain CC via Ableton's own MIDI Map, same as
        # everything else on the Master page.
        stems = rig_config.get("stems") or []
        self._stem_count = len(stems)
        self._stem_track_bindings = [s.get("trackName") for s in stems]
        self._stem_labels = [s.get("label") for s in stems]

        # Loopers: separate dedicated loop tracks, bound by trackName (no
        # positional fallback, same as stems). Control is direct Live Object
        # Model manipulation of each track's native Looper device "State"
        # parameter -- not plain MIDI CC -- because the Looper device exposes
        # one combined State enum (Stop/Record/Play) rather than discrete
        # momentary buttons, which doesn't map cleanly via Ableton's Cmd+M.
        loopers = rig_config.get("loopers") or []
        self._looper_count = len(loopers)
        self._looper_track_bindings = [l.get("trackName") for l in loopers]
        self._looper_labels = [l.get("label") for l in loopers]

        with self.component_guard():
            self.log_message("LiveRig Remote Script loaded.")
            self.show_message("LiveRig connected")
            self._connect_listeners()
            # Push a full state snapshot to the bridge once we're up.
            self.schedule_message(2, self._emit_full_state)

    # ── Live tells us which ports the user assigned ─────────────────────────
    def suggest_input_port(self):
        return self._suggested_input_port

    def suggest_output_port(self):
        return self._suggested_output_port

    def can_lock_to_devices(self):
        return False

    # ── Listener wiring ─────────────────────────────────────────────────────
    def _connect_listeners(self):
        song = self.song()

        def safe_add(label, fn):
            try:
                fn()
            except Exception as e:
                self.log_message("Listener subscribe failed [%s]: %s" % (label, e))

        # Transport
        safe_add("is_playing",   lambda: song.add_is_playing_listener(self._on_playing_changed))
        safe_add("record_mode",  lambda: song.add_record_mode_listener(self._on_record_changed))
        safe_add("tempo",        lambda: song.add_tempo_listener(self._on_tempo_changed))
        # Cue points & scenes
        safe_add("cue_points",   lambda: song.add_cue_points_listener(self._on_cue_points_changed))
        safe_add("scenes",       lambda: song.add_scenes_listener(self._on_scenes_changed))
        # Selected track — different APIs across Live versions; try both
        try:
            song.view.add_selected_track_listener(self._on_selected_track_changed)
        except Exception as e1:
            try:
                # Some Live builds expose this on song.view differently
                self.application().view.add_is_view_visible_listener(self._on_selected_track_changed)
            except Exception as e2:
                self.log_message("selected_track listener failed: %s / %s" % (e1, e2))

        self._cue_name_listeners = []
        self._scene_name_listeners = []
        try: self._rebind_cue_listeners()
        except Exception as e: self.log_message("rebind_cue init: " + str(e))
        try: self._rebind_scene_listeners()
        except Exception as e: self.log_message("rebind_scene init: " + str(e))

        # Per-track macro listeners for KBD1-4
        self._macro_listeners = []
        try: self._rebind_macro_listeners()
        except Exception as e: self.log_message("rebind_macro init: " + str(e))

        # Per-track color listeners for KBD1-4 (so KBD tab / Master column
        # accents can follow whatever Ableton track color the user assigned)
        self._kbd_color_listeners = []
        try: self._rebind_kbd_color_listeners()
        except Exception as e: self.log_message("rebind_kbd_color init: " + str(e))
        try: self._emit_all_kbd_colors()
        except Exception as e: self.log_message("emit_all_kbd_colors init: " + str(e))

        # Per-track name listeners for KBD1-4 (so Master page K1-K4 labels
        # show the real Ableton track name instead of a static placeholder)
        self._kbd_name_listeners = []
        try: self._rebind_kbd_name_listeners()
        except Exception as e: self.log_message("rebind_kbd_name init: " + str(e))
        try: self._emit_all_kbd_names()
        except Exception as e: self.log_message("emit_all_kbd_names init: " + str(e))

        # Per-track color/name listeners for the stems list (independent of
        # KBD1-4, bound by rig_config's stems[].trackName)
        self._stem_color_listeners = []
        self._stem_name_listeners = []
        try: self._rebind_stem_color_listeners()
        except Exception as e: self.log_message("rebind_stem_color init: " + str(e))
        try: self._emit_all_stem_colors()
        except Exception as e: self.log_message("emit_all_stem_colors init: " + str(e))
        try: self._rebind_stem_name_listeners()
        except Exception as e: self.log_message("rebind_stem_name init: " + str(e))
        try: self._emit_all_stem_names()
        except Exception as e: self.log_message("emit_all_stem_names init: " + str(e))

        # Looper device "State" param listeners for loop1-4 (separate
        # dedicated loop tracks, bound via rig_config.json loopers[].trackName)
        # so the iPad UI shows true REC/PLAY/STOP rather than only the
        # optimistic state set locally on button-press.
        self._looper_state_listeners = []
        self._looper_state_maps = {}
        try: self._rebind_looper_state_listeners()
        except Exception as e: self.log_message("rebind_looper_state init: " + str(e))
        try: self._emit_all_looper_states()
        except Exception as e: self.log_message("emit_all_looper_states init: " + str(e))
        self._looper_quant_listeners = []
        try: self._rebind_looper_quant_listeners()
        except Exception as e: self.log_message("rebind_looper_quant init: " + str(e))
        try: self._emit_all_looper_quants()
        except Exception as e: self.log_message("emit_all_looper_quants init: " + str(e))

        # Re-bind macros/colors/names/stems if track devices change
        safe_add("tracks", lambda: song.add_tracks_listener(self._on_tracks_changed))

        # 10 Hz song-time poll
        self._song_time_poll_active = True
        try:
            self.schedule_message(1, self._poll_song_time_tick)
        except Exception as e:
            self.log_message("schedule_message init: " + str(e))

    def disconnect(self):
        self._song_time_poll_active = False
        song = self.song()
        def safe_remove(fn):
            try: fn()
            except Exception: pass
        safe_remove(lambda: song.remove_is_playing_listener(self._on_playing_changed))
        safe_remove(lambda: song.remove_record_mode_listener(self._on_record_changed))
        safe_remove(lambda: song.remove_tempo_listener(self._on_tempo_changed))
        safe_remove(lambda: song.remove_cue_points_listener(self._on_cue_points_changed))
        safe_remove(lambda: song.remove_scenes_listener(self._on_scenes_changed))
        safe_remove(lambda: song.view.remove_selected_track_listener(self._on_selected_track_changed))
        safe_remove(lambda: song.remove_tracks_listener(self._on_tracks_changed))
        try: self._unbind_cue_listeners()
        except Exception: pass
        try: self._unbind_scene_listeners()
        except Exception: pass
        try: self._unbind_macro_listeners()
        except Exception: pass
        try: self._unbind_kbd_color_listeners()
        except Exception: pass
        try: self._unbind_kbd_name_listeners()
        except Exception: pass
        try: self._unbind_stem_color_listeners()
        except Exception: pass
        try: self._unbind_stem_name_listeners()
        except Exception: pass
        try: self._unbind_looper_state_listeners()
        except Exception: pass
        try: self._unbind_looper_quant_listeners()
        except Exception: pass
        ControlSurface.disconnect(self)

    def _poll_song_time_tick(self):
        """Re-schedule self every 1 tick (~100ms). Emits song_time when playing.
        This replaces the per-audio-block current_song_time listener which
        stutters Live's audio thread.
        """
        if not getattr(self, "_song_time_poll_active", False):
            return
        try:
            song = self.song()
            if song.is_playing:
                self._emit_song_time()
        except Exception as e:
            self.log_message("song_time poll error: " + str(e))
        # Re-schedule. Live's schedule_message uses ticks; 1 tick = 100ms.
        self.schedule_message(1, self._poll_song_time_tick)

    # ── Listener callbacks ──────────────────────────────────────────────────
    def _on_playing_changed(self):
        self._emit_transport_state()

    def _on_record_changed(self):
        self._emit_transport_state()

    def _on_tempo_changed(self):
        self._emit_bpm()

    def _on_cue_points_changed(self):
        self._rebind_cue_listeners()
        self._emit_cue_list()

    def _on_scenes_changed(self):
        self._rebind_scene_listeners()
        self._emit_scene_list()

    def _on_selected_track_changed(self):
        self._emit_selected_track()

    def _on_tracks_changed(self):
        self._rebind_macro_listeners()
        self._emit_all_macros()
        self._rebind_kbd_color_listeners()
        self._emit_all_kbd_colors()
        self._rebind_kbd_name_listeners()
        self._emit_all_kbd_names()
        self._rebind_stem_color_listeners()
        self._emit_all_stem_colors()
        self._rebind_stem_name_listeners()
        self._emit_all_stem_names()
        self._rebind_looper_state_listeners()
        self._emit_all_looper_states()
        self._rebind_looper_quant_listeners()
        self._emit_all_looper_quants()

    # ── Cue-point name listeners (rebind on add/remove) ─────────────────────
    def _rebind_cue_listeners(self):
        self._unbind_cue_listeners()
        try:
            for cue in self.song().cue_points:
                listener = lambda c=cue: self._emit_cue_list()
                cue.add_name_listener(listener)
                cue.add_time_listener(listener)
                self._cue_name_listeners.append((cue, listener))
        except Exception as e:
            self.log_message("rebind cues error: " + str(e))

    def _unbind_cue_listeners(self):
        for cue, listener in self._cue_name_listeners:
            try:
                cue.remove_name_listener(listener)
                cue.remove_time_listener(listener)
            except Exception:
                pass
        self._cue_name_listeners = []

    # ── Scene name listeners ────────────────────────────────────────────────
    def _rebind_scene_listeners(self):
        self._unbind_scene_listeners()
        try:
            for scene in self.song().scenes:
                listener = lambda s=scene: self._emit_scene_list()
                scene.add_name_listener(listener)
                self._scene_name_listeners.append((scene, listener))
        except Exception as e:
            self.log_message("rebind scenes error: " + str(e))

    def _unbind_scene_listeners(self):
        for scene, listener in self._scene_name_listeners:
            try:
                scene.remove_name_listener(listener)
            except Exception:
                pass
        self._scene_name_listeners = []

    # ── Generic slot -> actual track resolution ──────────────────────────────
    def _resolve_track_binding(self, binding, label, fallback_idx):
        """Resolve a binding value (track name str, literal index, or None) to
        an actual index into self.song().tracks. `label` is just for logging
        (e.g. "kbd0" or "stem3"). `fallback_idx` is returned (clamped to a
        valid track index, or None) when the binding is unbound or a name
        match isn't found -- pass the KBD slot index for KBD1-4 (preserves
        the old positional behavior), or None for stems (no positional
        convention makes sense there).
        """
        tracks = self.song().tracks
        def clamped_fallback():
            if fallback_idx is not None and 0 <= fallback_idx < len(tracks):
                return fallback_idx
            return None
        if binding is None:
            result = clamped_fallback()
            self.log_message("%s resolve: unbound, fallback -> %s" % (label, result))
            return result
        if isinstance(binding, (int, float)):
            idx = int(binding)
            result = idx if 0 <= idx < len(tracks) else clamped_fallback()
            self.log_message("%s resolve: index binding %s -> %s" % (label, idx, result))
            return result
        # String: case-insensitive name match
        name = str(binding).strip().lower()
        for idx, track in enumerate(tracks):
            try:
                if (track.name or "").strip().lower() == name:
                    self.log_message("%s resolve: name '%s' matched track %d ('%s')" % (label, binding, idx, track.name))
                    return idx
            except Exception:
                continue
        # No match — fall back, preserving old KBD positional behavior
        result = clamped_fallback()
        all_names = [getattr(t, "name", "?") for t in tracks]
        self.log_message("%s resolve: name '%s' NOT FOUND among tracks %s -> fallback %s" % (label, binding, all_names, result))
        return result

    def _resolve_kbd_track_index(self, ti):
        """Resolve KBD slot `ti` (0-3) to an actual track index, using
        rig_config's defaultTrackBinding. Falls back to the old positional
        behavior (track index == KBD slot) if unbound or no match is found,
        so sets that don't use defaultTrackBinding keep working unchanged.
        """
        binding = self._track_bindings[ti] if ti < len(self._track_bindings) else None
        return self._resolve_track_binding(binding, "kbd%d" % ti, fallback_idx=ti)

    def _resolve_stem_track_index(self, si):
        """Resolve stem slot `si` to an actual track index, using rig_config's
        stems[si].trackName. No positional fallback -- stems are a distinct
        list with no natural correspondence to track order, so an unbound or
        unmatched stem just resolves to None (skipped) instead of guessing.
        """
        binding = self._stem_track_bindings[si] if si < len(self._stem_track_bindings) else None
        return self._resolve_track_binding(binding, "stem%d" % si, fallback_idx=None)

    def _resolve_looper_track_index(self, li):
        """Resolve loop slot `li` to an actual track index, using
        rig_config's loopers[li].trackName. No positional fallback -- loop
        tracks are dedicated and have no natural correspondence to KBD/stem
        order, so an unbound or unmatched loop slot just resolves to None
        (skipped) instead of guessing.
        """
        binding = self._looper_track_bindings[li] if li < len(self._looper_track_bindings) else None
        return self._resolve_track_binding(binding, "loop%d" % li, fallback_idx=None)

    # ── Macro listeners for KBD1-4 ──────────────────────────────────────────
    def _select_macro_params(self, device, bank_size):
        """Choose up to `bank_size` parameters to treat as fader-bound
        'macros' for feedback purposes.

        Racks have a fixed, curated Macro 1..bank_size convention -- always
        continuous by design -- so we mirror params[1..bank_size] back to the
        iPad faders for live visual feedback.

        Bare plugins/instruments have no such convention, and most users
        (including this rig) map individual plugin parameters directly to
        buttons/faders via Ableton's own MIDI Map mode -- a 1:1 assignment
        that Live's Python API has no way to introspect from a Control
        Surface script. Guessing "the first N continuous parameters" risks
        picking a parameter that's actually mapped to a button instead,
        which would make a fader visually mirror whatever the button is
        doing. So for non-Rack devices we deliberately return nothing: no
        feedback, but also zero risk of cross-talk between controls. Control
        routing itself (CC -> parameter) is untouched either way -- it's
        handled entirely by Ableton's own MIDI Map, not this script.
        """
        if not self._is_rack(device):
            return []
        try:
            params = device.parameters
        except Exception:
            return []
        return list(enumerate(params[1:bank_size + 1]))

    def _rebind_macro_listeners(self):
        """Rebind macro-value listeners for each KBD slot's bound track.
        Only tracks with an Instrument/Audio/MIDI Rack get live fader
        feedback (their Macro 1..bank_size parameters). Bare plugins are
        controlled entirely via Ableton's own MIDI Map (CC -> parameter,
        set up by the user) and get no feedback listener, so there's no way
        for this script to latch onto a parameter that's actually mapped to
        a button. Track resolution honors defaultTrackBinding.
        """
        self._unbind_macro_listeners()
        try:
            for ti in range(self._kbd_count):
                track_idx = self._resolve_kbd_track_index(ti)
                if track_idx is None:
                    self.log_message("kbd%d macro bind: no track resolved, skipping" % ti)
                    continue
                track = self.song().tracks[track_idx]
                device = self._find_first_device(track)
                if device is None:
                    self.log_message("kbd%d macro bind: track '%s' has no devices, skipping" % (ti, getattr(track, "name", "?")))
                    continue
                kind = "rack" if self._is_rack(device) else "plugin"
                bank_size = self._bank_sizes[ti] if ti < len(self._bank_sizes) else 8
                bound_count = 0
                for macro_idx, param in self._select_macro_params(device, bank_size):
                    kbd_idx = ti  # wire format still uses the KBD slot, not the track index
                    listener = lambda p=param, t=kbd_idx, m=macro_idx: \
                        self._emit_macro_value(t, m, p)
                    param.add_value_listener(listener)
                    self._macro_listeners.append((param, listener))
                    bound_count += 1
                self.log_message("kbd%d macro bind: track '%s', %s '%s', bound %d listeners" % (ti, getattr(track, "name", "?"), kind, getattr(device, "name", "?"), bound_count))
        except Exception as e:
            self.log_message("rebind macros error: " + str(e))

    def _unbind_macro_listeners(self):
        for param, listener in self._macro_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._macro_listeners = []

    @staticmethod
    def _is_rack(dev):
        cls = getattr(dev, "class_name", "") or ""
        return "GroupDevice" in cls  # Instrument/Audio/MidiEffectGroupDevice

    def _find_first_device(self, track):
        """Return the first device on `track`, preferring a Rack if one is
        present anywhere in the chain (so a Rack later in the device list
        still wins over an earlier plain plugin), else the first device of
        any kind. Returns None if the track has no devices at all."""
        try:
            devices = list(track.devices)
            if not devices:
                return None
            for dev in devices:
                if self._is_rack(dev):
                    return dev
            return devices[0]
        except Exception:
            return None

    # ── Track-color listeners for KBD1-4 ────────────────────────────────────
    def _rebind_kbd_color_listeners(self):
        """Rebind color-change listeners for each KBD slot's bound track
        (resolved the same way as macros) so the iPad UI can mirror whatever
        color the user assigned to that track in Ableton."""
        self._unbind_kbd_color_listeners()
        try:
            for ti in range(self._kbd_count):
                track_idx = self._resolve_kbd_track_index(ti)
                if track_idx is None:
                    self.log_message("kbd%d color bind: no track resolved, skipping" % ti)
                    continue
                track = self.song().tracks[track_idx]
                kbd_idx = ti
                listener = lambda t=kbd_idx: self._emit_kbd_color(t)
                track.add_color_listener(listener)
                self._kbd_color_listeners.append((track, listener))
                self.log_message("kbd%d color bind: track '%s' color=%s" % (ti, getattr(track, "name", "?"), getattr(track, "color", "?")))
        except Exception as e:
            self.log_message("rebind kbd color error: " + str(e))

    def _unbind_kbd_color_listeners(self):
        for track, listener in self._kbd_color_listeners:
            try:
                track.remove_color_listener(listener)
            except Exception:
                pass
        self._kbd_color_listeners = []

    # ── Track-name listeners for KBD1-4 ─────────────────────────────────────
    def _rebind_kbd_name_listeners(self):
        """Rebind name-change listeners for each KBD slot's bound track
        (resolved the same way as macros/colors) so the iPad UI's Master
        page K1-K4 labels can show the real Ableton track name."""
        self._unbind_kbd_name_listeners()
        try:
            for ti in range(self._kbd_count):
                track_idx = self._resolve_kbd_track_index(ti)
                if track_idx is None:
                    self.log_message("kbd%d name bind: no track resolved, skipping" % ti)
                    continue
                track = self.song().tracks[track_idx]
                kbd_idx = ti
                listener = lambda t=kbd_idx: self._emit_kbd_name(t)
                track.add_name_listener(listener)
                self._kbd_name_listeners.append((track, listener))
                self.log_message("kbd%d name bind: track '%s'" % (ti, getattr(track, "name", "?")))
        except Exception as e:
            self.log_message("rebind kbd name error: " + str(e))

    def _unbind_kbd_name_listeners(self):
        for track, listener in self._kbd_name_listeners:
            try:
                track.remove_name_listener(listener)
            except Exception:
                pass
        self._kbd_name_listeners = []

    # ── Track-color listeners for stems[] (Master page stem channels) ───────
    def _rebind_stem_color_listeners(self):
        """Rebind color-change listeners for each stem's bound track
        (resolved via rig_config.json stems[].trackName, no positional
        fallback) so the iPad UI can mirror the track's Ableton color."""
        self._unbind_stem_color_listeners()
        try:
            for si in range(self._stem_count):
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is None:
                    self.log_message("stem%d color bind: no track resolved, skipping" % si)
                    continue
                track = self.song().tracks[track_idx]
                stem_idx = si
                listener = lambda t=stem_idx: self._emit_stem_color(t)
                track.add_color_listener(listener)
                self._stem_color_listeners.append((track, listener))
                self.log_message("stem%d color bind: track '%s' color=%s" % (si, getattr(track, "name", "?"), getattr(track, "color", "?")))
        except Exception as e:
            self.log_message("rebind stem color error: " + str(e))

    def _unbind_stem_color_listeners(self):
        for track, listener in self._stem_color_listeners:
            try:
                track.remove_color_listener(listener)
            except Exception:
                pass
        self._stem_color_listeners = []

    # ── Track-name listeners for stems[] (Master page stem channels) ────────
    def _rebind_stem_name_listeners(self):
        """Rebind name-change listeners for each stem's bound track
        (resolved the same way as stem colors) so the iPad UI's stem
        channel labels can show the real Ableton track name."""
        self._unbind_stem_name_listeners()
        try:
            for si in range(self._stem_count):
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is None:
                    self.log_message("stem%d name bind: no track resolved, skipping" % si)
                    continue
                track = self.song().tracks[track_idx]
                stem_idx = si
                listener = lambda t=stem_idx: self._emit_stem_name(t)
                track.add_name_listener(listener)
                self._stem_name_listeners.append((track, listener))
                self.log_message("stem%d name bind: track '%s'" % (si, getattr(track, "name", "?")))
        except Exception as e:
            self.log_message("rebind stem name error: " + str(e))

    def _unbind_stem_name_listeners(self):
        for track, listener in self._stem_name_listeners:
            try:
                track.remove_name_listener(listener)
            except Exception:
                pass
        self._stem_name_listeners = []

    # ── Looper device control (loop1-4, native Live Object Model control) ───
    def _find_looper_device(self, track):
        """Return the first Looper device found on `track`, or None.
        Matches by class_name (stable across renaming) rather than the
        device's display name."""
        try:
            for dev in track.devices:
                if getattr(dev, "class_name", "") == "Looper":
                    return dev
        except Exception:
            pass
        return None

    def _get_looper_state_map(self, device):
        """Find the Looper device's 'State' parameter and map its named
        value_items (e.g. 'Stop'/'Record'/'Play') to enum indices via a
        case-insensitive substring match, rather than hardcoding indices --
        Ableton's exact enum ordering for this parameter isn't something we
        should assume. Returns (param, {'rec':i,'play':i,'stop':i}); param
        is None and the dict is empty if not found."""
        try:
            for p in device.parameters:
                if (p.name or "").strip().lower() != "state":
                    continue
                items = [str(v).strip().lower() for v in (p.value_items or [])]
                idx_map = {}
                for i, name in enumerate(items):
                    if "rec" in name:
                        idx_map["rec"] = i
                    elif "play" in name:
                        idx_map["play"] = i
                    elif "stop" in name:
                        idx_map["stop"] = i
                return p, idx_map
        except Exception as e:
            self.log_message("looper state map error: " + str(e))
        return None, {}

    def _looper_set_state(self, li, target):
        """Set loop slot `li`'s Looper device State param to `target`
        ('rec'|'play'|'stop'). No-ops (with a log line) if the track,
        device, or parameter can't be resolved -- never guesses."""
        try:
            track_idx = self._resolve_looper_track_index(li)
            if track_idx is None:
                self.log_message("loop%d set_state(%s): no track resolved, skipping" % (li, target))
                return
            track = self.song().tracks[track_idx]
            device = self._find_looper_device(track)
            if device is None:
                self.log_message("loop%d set_state(%s): no Looper device on track '%s', skipping" % (li, target, getattr(track, "name", "?")))
                return
            param, idx_map = self._get_looper_state_map(device)
            if param is None or target not in idx_map:
                self.log_message("loop%d set_state(%s): Looper 'State' param/value not found, skipping" % (li, target))
                return
            before = param.value
            target_val = idx_map[target]
            # The Looper's State param is a no-op via the Live API while the
            # song transport is stopped (confirmed: Ableton/M4L community --
            # writes are silently ignored unless Live's global transport is
            # already running). Auto-start it, mirroring what pressing the
            # device's own on-screen button does.
            try:
                if not self.song().is_playing:
                    self.log_message("loop%d set_state(%s): transport stopped, starting playback" % (li, target))
                    self.song().start_playing()
            except Exception as e:
                self.log_message("loop%d set_state(%s): start_playing failed: %s" % (li, target, e))
            self.log_message("loop%d set_state(%s): device='%s' param='%s' is_enabled=%s min=%s max=%s before=%s target=%s" % (
                li, target, getattr(device, "name", "?"), param.name,
                getattr(param, "is_enabled", "?"), param.min, param.max, before, target_val))
            param.value = target_val
            after = param.value
            self.log_message("loop%d set_state(%s): after=%s (%s)" % (
                li, target, after, "OK" if after == target_val else "DID NOT STICK"))
        except Exception as e:
            self.log_message("loop%d set_state(%s) error: %s" % (li, target, e))

    def _looper_clear_pulse_param(self, param):
        try:
            param.value = 0
        except Exception:
            pass

    def _looper_undo(self, li):
        """Momentarily pulse the Looper device's 'Undo' param (0->1->0) if
        present. Deliberately has no fallback to song-level undo -- that
        would undo unrelated edits elsewhere in the set, not just the loop."""
        try:
            track_idx = self._resolve_looper_track_index(li)
            if track_idx is None:
                self.log_message("loop%d undo: no track resolved, skipping" % li)
                return
            track = self.song().tracks[track_idx]
            device = self._find_looper_device(track)
            if device is None:
                self.log_message("loop%d undo: no Looper device on track '%s', skipping" % (li, getattr(track, "name", "?")))
                return
            for p in device.parameters:
                if (p.name or "").strip().lower() == "undo":
                    p.value = 1
                    self.schedule_message(1, lambda p=p: self._looper_clear_pulse_param(p))
                    return
            self.log_message("loop%d undo: Looper 'Undo' param not found, skipping" % li)
        except Exception as e:
            self.log_message("loop%d undo error: %s" % (li, e))

    # ── Looper State-param listeners (feedback: true REC/PLAY/STOP) ─────────
    def _rebind_looper_state_listeners(self):
        self._unbind_looper_state_listeners()
        self._looper_state_maps = {}
        try:
            for li in range(self._looper_count):
                track_idx = self._resolve_looper_track_index(li)
                if track_idx is None:
                    self.log_message("loop%d state bind: no track resolved, skipping" % li)
                    continue
                track = self.song().tracks[track_idx]
                device = self._find_looper_device(track)
                if device is None:
                    self.log_message("loop%d state bind: no Looper device on track '%s', skipping" % (li, getattr(track, "name", "?")))
                    continue
                param, idx_map = self._get_looper_state_map(device)
                if param is None:
                    self.log_message("loop%d state bind: Looper 'State' param not found, skipping" % li)
                    continue
                self._looper_state_maps[li] = idx_map
                loop_idx = li
                listener = lambda l=loop_idx: self._emit_looper_state(l)
                param.add_value_listener(listener)
                self._looper_state_listeners.append((param, listener))
                self.log_message("loop%d state bind: track '%s', map=%s" % (li, getattr(track, "name", "?"), idx_map))
        except Exception as e:
            self.log_message("rebind looper state error: " + str(e))

    def _unbind_looper_state_listeners(self):
        for param, listener in self._looper_state_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._looper_state_listeners = []

    # ── Looper Quantization control (bar-length selector) ───────────────────
    def _get_looper_quant_param(self, device):
        """Return the Looper device's 'Quantization' parameter, or None.
        Its value_items are confirmed (via diagnostic dump) to be:
        ['Global','None','8 Bars','4 Bars','2 Bars','1 Bar','1/2','1/2T',
         '1/4','1/4T','1/8','1/8T','1/16','1/16T','1/32']."""
        try:
            for p in device.parameters:
                if (p.name or "").strip().lower() == "quantization":
                    return p
        except Exception:
            pass
        return None

    def _looper_set_quantization(self, li, quant_idx):
        """Set loop slot `li`'s Looper device Quantization param to the
        enum index `quant_idx` (sent by the UI dropdown). No-ops (with a
        log line) if the track/device/param can't be resolved or the
        index is out of range -- never guesses or clamps silently."""
        try:
            track_idx = self._resolve_looper_track_index(li)
            if track_idx is None:
                self.log_message("loop%d set_quant(%s): no track resolved, skipping" % (li, quant_idx))
                return
            track = self.song().tracks[track_idx]
            device = self._find_looper_device(track)
            if device is None:
                self.log_message("loop%d set_quant(%s): no Looper device on track '%s', skipping" % (li, quant_idx, getattr(track, "name", "?")))
                return
            param = self._get_looper_quant_param(device)
            if param is None:
                self.log_message("loop%d set_quant(%s): Looper 'Quantization' param not found, skipping" % (li, quant_idx))
                return
            if quant_idx < param.min or quant_idx > param.max:
                self.log_message("loop%d set_quant(%s): out of range (min=%s max=%s), skipping" % (li, quant_idx, param.min, param.max))
                return
            before = param.value
            param.value = quant_idx
            after = param.value
            self.log_message("loop%d set_quant(%s): before=%s after=%s (%s)" % (
                li, quant_idx, before, after, "OK" if after == quant_idx else "DID NOT STICK"))
        except Exception as e:
            self.log_message("loop%d set_quant(%s) error: %s" % (li, quant_idx, e))

    def _emit_looper_quant(self, li):
        try:
            track_idx = self._resolve_looper_track_index(li)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            device = self._find_looper_device(track)
            if device is None:
                return
            param = self._get_looper_quant_param(device)
            if param is None:
                return
            quant_idx = int(round(param.value))
            self._send_sx([FB_LOOP_QUANT, li & 0x7F, quant_idx & 0x7F])
        except Exception as e:
            self.log_message("looper quant emit error: " + str(e))

    def _emit_all_looper_quants(self):
        for li in range(self._looper_count):
            self._emit_looper_quant(li)

    def _rebind_looper_quant_listeners(self):
        self._unbind_looper_quant_listeners()
        try:
            for li in range(self._looper_count):
                track_idx = self._resolve_looper_track_index(li)
                if track_idx is None:
                    continue
                track = self.song().tracks[track_idx]
                device = self._find_looper_device(track)
                if device is None:
                    continue
                param = self._get_looper_quant_param(device)
                if param is None:
                    continue
                loop_idx = li
                listener = lambda l=loop_idx: self._emit_looper_quant(l)
                param.add_value_listener(listener)
                self._looper_quant_listeners.append((param, listener))
        except Exception as e:
            self.log_message("rebind looper quant error: " + str(e))

    def _unbind_looper_quant_listeners(self):
        for param, listener in self._looper_quant_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._looper_quant_listeners = []

    # ── MIDI map registration — tells Live to forward these CCs to receive_midi ─
    def build_midi_map(self, midi_map_handle):
        """Register CCs that LiveRig handles directly in Python.
        Registered CCs are forwarded to receive_midi; they do NOT reach
        Ableton's own MIDI map, so remove any conflicting CMD+M mappings.

        Handled here:
          KBD mute/solo  — CC1/CC2 on each keyboard's MIDI channel (dynamic,
                           self._kbd_channels — was hardcoded ch1-4)
          Stem mute/solo — CC N+1..3N on MIDI ch6  (dynamic per STEM_COUNT)
          FX returns     — CC1-12 on MIDI ch7      (vol + mute + solo)
        """
        # KBD mute (CC1) and solo (CC2) on each keyboard's assigned channel
        for ch in self._kbd_channels:
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, ch, 1)
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, ch, 2)
        # Stem mute/solo on MIDI ch6 (index 5): CC N+1 .. 3N
        n = self._stem_count
        for cc in range(n + 1, 3 * n + 1):
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, 5, cc)
        # FX Return vol+mute+solo on MIDI ch7 (index 6): CC1-12
        for cc in range(1, 13):
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, 6, cc)

    # ── Inbound MIDI — SysEx commands + registered CC handlers ───────────────
    def receive_midi(self, midi_bytes):
        if not midi_bytes:
            return
        status = midi_bytes[0] & 0xF0

        # SysEx (F0 7D …)
        if status == 0xF0:
            if len(midi_bytes) < 4 or midi_bytes[1] != LIVERIG_MFG_ID:
                return
            if midi_bytes[-1] != 0xF7:
                return
            code = midi_bytes[2] & 0x7F
            value = midi_bytes[3] & 0x7F if len(midi_bytes) >= 5 else 0
            try:
                self._dispatch_sysex(code, value)
            except Exception as e:
                self.log_message("dispatch error code=" + hex(code) + ": " + str(e))
            return

        # CC (0xB0-0xBF) — only reaches here if registered in build_midi_map
        if status == 0xB0:
            if len(midi_bytes) < 3:
                return
            ch  = midi_bytes[0] & 0x0F   # 0-indexed channel
            cc  = midi_bytes[1] & 0x7F
            val = midi_bytes[2] & 0x7F
            try:
                self._dispatch_cc(ch, cc, val)
            except Exception as e:
                self.log_message(
                    "cc error ch=%d cc=%d val=%d: %s" % (ch + 1, cc, val, str(e)))

    def _dispatch_cc(self, channel, cc, val):
        """Route registered inbound CC messages to Live track parameters.
        channel is 0-indexed (0 = MIDI ch1).
        """
        song = self.song()

        # ── KBD tracks: each keyboard's assigned channel, CC1=mute, CC2=solo ──
        # (was hardcoded "0 <= channel <= 3" assuming channel index == KBD
        # slot; now resolved via self._kbd_channel_to_index so KBD5+ on any
        # free channel still routes correctly.)
        if channel in self._kbd_channel_to_index and cc in (1, 2):
            ti = self._kbd_channel_to_index[channel]
            track_idx = self._resolve_kbd_track_index(ti)
            if track_idx is None:
                return
            try:
                track = song.tracks[track_idx]
                if cc == 1:
                    track.mute = bool(val)
                else:
                    track.solo = bool(val)
            except Exception as e:
                self.log_message("kbd%d mute/solo error: %s" % (ti, str(e)))
            return

        # ── Stems: MIDI ch6 (index 5), mute/solo ─────────────────────────────
        if channel == 5:
            n = self._stem_count
            if n == 0:
                return
            # mutes:  CC N+1 .. 2N
            if n + 1 <= cc <= 2 * n:
                si = cc - n - 1
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is not None:
                    try:
                        song.tracks[track_idx].mute = bool(val)
                    except Exception:
                        pass
            # solos:  CC 2N+1 .. 3N
            elif 2 * n + 1 <= cc <= 3 * n:
                si = cc - 2 * n - 1
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is not None:
                    try:
                        song.tracks[track_idx].solo = bool(val)
                    except Exception:
                        pass
            return

        # ── FX Return tracks: MIDI ch7 (index 6) ─────────────────────────────
        # vol:  CC1-4  → return_tracks[0-3].mixer_device.volume
        # mute: CC5-8  → return_tracks[0-3].mute
        # solo: CC9-12 → return_tracks[0-3].solo
        if channel == 6:
            ret_tracks = list(song.return_tracks)
            if 1 <= cc <= 4:
                ri = cc - 1
                if ri < len(ret_tracks):
                    try:
                        ret_tracks[ri].mixer_device.volume.value = val / 127.0
                    except Exception:
                        pass
            elif 5 <= cc <= 8:
                ri = cc - 5
                if ri < len(ret_tracks):
                    try:
                        ret_tracks[ri].mute = bool(val)
                    except Exception:
                        pass
            elif 9 <= cc <= 12:
                ri = cc - 9
                if ri < len(ret_tracks):
                    try:
                        ret_tracks[ri].solo = bool(val)
                    except Exception:
                        pass
            return

    def _dispatch_sysex(self, code, value):
        song = self.song()
        if code == SX_LOCATOR_JUMP:
            cps = list(song.cue_points)
            if 0 <= value < len(cps):
                cps[value].jump()
        elif code == SX_LOCATOR_NEXT:
            song.jump_to_next_cue()
        elif code == SX_LOCATOR_PREV:
            song.jump_to_prev_cue()
        elif code == SX_SCENE_FIRE:
            scenes = list(song.scenes)
            if 0 <= value < len(scenes):
                scenes[value].fire()
        elif code == SX_PLAY:
            song.start_playing()
        elif code == SX_STOP:
            song.stop_playing()
        elif code == SX_RECORD:
            song.record_mode = 0 if song.record_mode else 1
        elif code == SX_OVERDUB:
            song.overdub = 0 if song.overdub else 1
        elif code == SX_METRO:
            song.metronome = 0 if song.metronome else 1
        elif code == SX_LOOP:
            song.loop = 0 if song.loop else 1
        elif code == SX_PUNCH_IN:
            song.punch_in = 0 if song.punch_in else 1
        elif code == SX_TAP_TEMPO:
            song.tap_tempo()
        elif code == SX_UNDO:
            if song.can_undo:
                song.undo()
        elif code == SX_REDO:
            if song.can_redo:
                song.redo()
        elif code == SX_REQUEST_FULL_STATE:
            self._emit_full_state()
        elif code == SX_LOOP_REC:
            self.log_message("dispatch: SX_LOOP_REC value=%s" % value)
            self._looper_set_state(value, "rec")
        elif code == SX_LOOP_PLAY:
            self.log_message("dispatch: SX_LOOP_PLAY value=%s" % value)
            self._looper_set_state(value, "play")
        elif code == SX_LOOP_STOP:
            self.log_message("dispatch: SX_LOOP_STOP value=%s" % value)
            self._looper_set_state(value, "stop")
        elif code == SX_LOOP_UNDO:
            self.log_message("dispatch: SX_LOOP_UNDO value=%s" % value)
            self._looper_undo(value)
        elif code == SX_LOOP_QUANT:
            loop_idx = (value >> 4) & 0x07
            quant_idx = value & 0x0F
            self.log_message("dispatch: SX_LOOP_QUANT loop=%s quant=%s" % (loop_idx, quant_idx))
            self._looper_set_quantization(loop_idx, quant_idx)

    # ── Outbound feedback emitters ──────────────────────────────────────────
    def _send_sx(self, body_bytes):
        """Send SysEx F0 7D 60 <body> F7."""
        msg = (0xF0, LIVERIG_MFG_ID, SX_FB_PREFIX) + tuple(body_bytes) + (0xF7,)
        try:
            self._send_midi(msg)
        except Exception as e:
            self.log_message("send_midi error: " + str(e))

    @staticmethod
    def _encode_str(s):
        """Encode unicode string into a list of 7-bit bytes prefixed by length.
        Length max 127. Non-ASCII chars are best-effort transliterated."""
        if s is None:
            return [0]
        try:
            data = s.encode("ascii", "replace")
        except Exception:
            data = b"?"
        if len(data) > 120:
            data = data[:120]
        out = [len(data)]
        for b in data:
            out.append(b & 0x7F)
        return out

    @staticmethod
    def _encode_uint14(v):
        v = max(0, min(0x3FFF, int(v)))
        return [(v >> 7) & 0x7F, v & 0x7F]

    @staticmethod
    def _encode_uint28(v):
        """Encode a 28-bit unsigned int into 4 7-bit bytes (big-endian)."""
        v = max(0, min(0x0FFFFFFF, int(v)))
        return [(v >> 21) & 0x7F, (v >> 14) & 0x7F, (v >> 7) & 0x7F, v & 0x7F]

    def _emit_transport_state(self):
        s = self.song()
        state = 0
        if s.is_playing:
            state = 2 if s.record_mode else 1
        self._send_sx([FB_TRANSPORT, state])

    def _emit_bpm(self):
        bpm = self.song().tempo
        self._send_sx([FB_BPM] + self._encode_uint14(int(round(bpm * 100))))

    def _emit_song_time(self):
        # song time is in beats (float). Multiply by 1000 and clamp.
        t_ms = int(self.song().current_song_time * 1000)
        self._send_sx([FB_SONG_TIME] + self._encode_uint28(t_ms))

    def _emit_song_len(self):
        t_ms = int(self.song().last_event_time * 1000)
        self._send_sx([FB_SONG_LEN] + self._encode_uint28(t_ms))

    def _emit_cue_list(self):
        cps = list(self.song().cue_points)
        self._send_sx([FB_CUE_LIST_BEGIN, len(cps) & 0x7F])
        for i, cue in enumerate(cps):
            try:
                name = cue.name
                t_ms = int(cue.time * 1000)
            except Exception:
                continue
            body = [FB_CUE_UPDATE, i & 0x7F]
            body += self._encode_uint28(t_ms)
            body += self._encode_str(name)
            self._send_sx(body)
        self._send_sx([FB_CUE_LIST_END])

    def _emit_scene_list(self):
        scenes = list(self.song().scenes)
        self._send_sx([FB_SCENE_LIST_BEGIN, len(scenes) & 0x7F])
        for i, sc in enumerate(scenes):
            try:
                name = sc.name
            except Exception:
                continue
            body = [FB_SCENE_UPDATE, i & 0x7F]
            body += self._encode_str(name)
            self._send_sx(body)
        self._send_sx([FB_SCENE_LIST_END])

    def _emit_selected_track(self):
        try:
            sel = self.song().view.selected_track
            tracks = list(self.song().tracks) + list(self.song().return_tracks)
            try:
                idx = tracks.index(sel)
            except ValueError:
                idx = 0x7F  # master/unknown
            name = sel.name if sel is not None else ""
            body = [FB_SELECTED_TRACK, idx & 0x7F]
            body += self._encode_str(name)
            self._send_sx(body)
        except Exception as e:
            self.log_message("selected track emit error: " + str(e))

    def _emit_macro_value(self, track_idx, macro_idx, param):
        try:
            # Normalize macro value to 14-bit range based on parameter min/max
            pmin = param.min
            pmax = param.max
            rng = (pmax - pmin) if (pmax - pmin) != 0 else 1
            norm = (param.value - pmin) / float(rng)
            v14 = int(round(max(0.0, min(1.0, norm)) * 0x3FFF))
            body = [FB_MACRO_VALUE, track_idx & 0x7F, macro_idx & 0x7F]
            body += self._encode_uint14(v14)
            body += self._encode_str(param.name)
            self._send_sx(body)
        except Exception as e:
            self.log_message("macro emit error: " + str(e))

    def _emit_all_macros(self):
        # Re-scan via the same name-based resolution used to bind listeners,
        # so a fresh full-state push matches whatever is actually listening.
        try:
            for ti in range(self._kbd_count):
                track_idx = self._resolve_kbd_track_index(ti)
                if track_idx is None:
                    continue
                device = self._find_first_device(self.song().tracks[track_idx])
                if device is None:
                    continue
                bank_size = self._bank_sizes[ti] if ti < len(self._bank_sizes) else 8
                for macro_idx, param in self._select_macro_params(device, bank_size):
                    self._emit_macro_value(ti, macro_idx, param)
        except Exception as e:
            self.log_message("emit all macros error: " + str(e))

    def _emit_kbd_color(self, ti):
        """Send the Ableton track color bound to KBD slot `ti` as RGB."""
        try:
            track_idx = self._resolve_kbd_track_index(ti)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            rgb = track.color  # plain int, e.g. 0xRRGGBB
            r = (rgb >> 16) & 0xFF
            g = (rgb >> 8) & 0xFF
            b = rgb & 0xFF
            body = [FB_KBD_COLOR, ti & 0x7F]
            body += self._encode_uint14(r)
            body += self._encode_uint14(g)
            body += self._encode_uint14(b)
            self._send_sx(body)
        except Exception as e:
            self.log_message("kbd color emit error: " + str(e))

    def _emit_all_kbd_colors(self):
        for ti in range(self._kbd_count):
            self._emit_kbd_color(ti)

    def _emit_kbd_name(self, ti):
        """Send the real Ableton track name bound to KBD slot `ti`, so the
        iPad UI (Master page K1-K4 labels) can show the actual track name
        instead of a static 'K1'..'K4' placeholder."""
        try:
            track_idx = self._resolve_kbd_track_index(ti)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            body = [FB_KBD_NAME, ti & 0x7F]
            body += self._encode_str(track.name)
            self._send_sx(body)
        except Exception as e:
            self.log_message("kbd name emit error: " + str(e))

    def _emit_all_kbd_names(self):
        for ti in range(self._kbd_count):
            self._emit_kbd_name(ti)

    def _emit_stem_color(self, si):
        """Send the Ableton track color bound to stem slot `si` as RGB."""
        try:
            track_idx = self._resolve_stem_track_index(si)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            rgb = track.color  # plain int, e.g. 0xRRGGBB
            r = (rgb >> 16) & 0xFF
            g = (rgb >> 8) & 0xFF
            b = rgb & 0xFF
            body = [FB_STEM_COLOR, si & 0x7F]
            body += self._encode_uint14(r)
            body += self._encode_uint14(g)
            body += self._encode_uint14(b)
            self._send_sx(body)
        except Exception as e:
            self.log_message("stem color emit error: " + str(e))

    def _emit_all_stem_colors(self):
        for si in range(self._stem_count):
            self._emit_stem_color(si)

    def _emit_stem_name(self, si):
        """Send the real Ableton track name bound to stem slot `si`, so the
        iPad UI's stem channel labels show the actual track name instead of
        a static 'Stem 1'..'Stem 8' placeholder."""
        try:
            track_idx = self._resolve_stem_track_index(si)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            body = [FB_STEM_NAME, si & 0x7F]
            body += self._encode_str(track.name)
            self._send_sx(body)
        except Exception as e:
            self.log_message("stem name emit error: " + str(e))

    def _emit_all_stem_names(self):
        for si in range(self._stem_count):
            self._emit_stem_name(si)

    def _emit_looper_state(self, li):
        """Send current Looper device state for loop slot `li` as
        0=stop, 1=record, 2=play (matches the FB_TRANSPORT convention)."""
        try:
            track_idx = self._resolve_looper_track_index(li)
            if track_idx is None:
                return
            track = self.song().tracks[track_idx]
            device = self._find_looper_device(track)
            if device is None:
                return
            param, idx_map = self._get_looper_state_map(device)
            if param is None:
                return
            cur = int(round(param.value))
            state = 0
            if idx_map.get("rec") == cur:
                state = 1
            elif idx_map.get("play") == cur:
                state = 2
            self._send_sx([FB_LOOP_STATE, li & 0x7F, state & 0x7F])
        except Exception as e:
            self.log_message("looper state emit error: " + str(e))

    def _emit_all_looper_states(self):
        for li in range(self._looper_count):
            self._emit_looper_state(li)

    def _emit_full_state(self):
        self._emit_transport_state()
        self._emit_bpm()
        self._emit_song_time()
        self._emit_song_len()
        self._emit_cue_list()
        self._emit_scene_list()
        self._emit_selected_track()
        self._emit_all_macros()
        self._emit_all_kbd_colors()
        self._emit_all_kbd_names()
        self._emit_all_stem_colors()
        self._emit_all_stem_names()
        self._emit_all_looper_states()
        self._emit_all_looper_quants()
