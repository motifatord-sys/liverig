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
"""
from __future__ import absolute_import, print_function, unicode_literals

import Live
from _Framework.ControlSurface import ControlSurface

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

LIVERIG_MFG_ID     = 0x7D


class LiveRig(ControlSurface):
    """Top-level Remote Script class. Live instantiates this once."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._suppress_send_midi = False
        self._suggested_input_port = "LiveRig Bridge"
        self._suggested_output_port = "LiveRig Bridge"

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

        # Re-bind macros if track devices change
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

    # ── Macro listeners for KBD1-4 (tracks 0-3) ─────────────────────────────
    def _rebind_macro_listeners(self):
        """Rebind macro-value listeners for the first 4 tracks if they have an
        Instrument Rack. Macros are device parameters 1-8 (param 0 = Device On).
        """
        self._unbind_macro_listeners()
        try:
            tracks = self.song().tracks
            for ti in range(min(4, len(tracks))):
                track = tracks[ti]
                rack = self._find_first_rack(track)
                if rack is None:
                    continue
                params = rack.parameters
                # Macros are params[1..8]
                for mi in range(1, min(9, len(params))):
                    param = params[mi]
                    track_idx = ti
                    macro_idx = mi - 1  # 0-based for the wire format
                    listener = lambda p=param, t=track_idx, m=macro_idx: \
                        self._emit_macro_value(t, m, p)
                    param.add_value_listener(listener)
                    self._macro_listeners.append((param, listener))
        except Exception as e:
            self.log_message("rebind macros error: " + str(e))

    def _unbind_macro_listeners(self):
        for param, listener in self._macro_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._macro_listeners = []

    def _find_first_rack(self, track):
        try:
            for dev in track.devices:
                cls = getattr(dev, "class_name", "") or ""
                if "GroupDevice" in cls:  # Instrument/Audio/MidiEffectGroupDevice
                    return dev
        except Exception:
            pass
        return None

    # ── Inbound SysEx — Live calls receive_midi for control-surface MIDI ────
    def receive_midi(self, midi_bytes):
        # Only handle SysEx beginning with F0 7D
        if len(midi_bytes) < 4 or midi_bytes[0] != 0xF0:
            return
        if midi_bytes[1] != LIVERIG_MFG_ID:
            return
        if midi_bytes[-1] != 0xF7:
            return
        code = midi_bytes[2] & 0x7F
        value = midi_bytes[3] & 0x7F if len(midi_bytes) >= 5 else 0
        try:
            self._dispatch_sysex(code, value)
        except Exception as e:
            self.log_message("dispatch error code=" + hex(code) + ": " + str(e))

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
        for param, _ in self._macro_listeners:
            try:
                # Find the (track_idx, macro_idx) for this param
                # by re-scanning. Cheap, runs once per re-bind.
                pass
            except Exception:
                pass
        # Simpler: re-scan and emit
        try:
            tracks = self.song().tracks
            for ti in range(min(4, len(tracks))):
                rack = self._find_first_rack(tracks[ti])
                if rack is None:
                    continue
                for mi in range(1, min(9, len(rack.parameters))):
                    self._emit_macro_value(ti, mi - 1, rack.parameters[mi])
        except Exception as e:
            self.log_message("emit all macros error: " + str(e))

    def _emit_full_state(self):
        self._emit_transport_state()
        self._emit_bpm()
        self._emit_song_time()
        self._emit_song_len()
        self._emit_cue_list()
        self._emit_scene_list()
        self._emit_selected_track()
        self._emit_all_macros()
