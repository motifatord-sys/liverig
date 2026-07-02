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
  0x50 = clip track name    | data: track_idx, name length, name bytes
  0x51 = clip info          | data: scene_idx, track_idx, flags, name length, name bytes
                                     flags bit0=has_clip bit1=playing bit2=triggered
                                     bit3=recording (matches Ableton's own Session
                                     View clip-slot visual states)
  0x56 = binding status     | data: category (0=kbd,1=stem,2=looper,3=aux), idx, status
                                     status: 0=ok 1=ok_positional 2=unbound
                                     3=ambiguous(duplicate track name) 4=empty(unconfigured)
                                     5=fallback_mismatch(named binding didn't match, using position)

Direct clip control (Session View, native Live Object Model — not fake
MIDI notes/CCs):
  0x52 = clip fire   | value: (scene_idx<<3)|track_idx -> ClipSlot.fire()
  0x53 = clip stop track | value: track_idx -> Track.stop_all_clips()
  0x54 = clip stop all   | value: unused -> Song.stop_all_clips()

Direct CC handling (via build_midi_map — no CMD+M needed for these):
  KBD    CC7=volume, CC1=mute, CC2=solo → KBD track vol/mute/solo (resolves
         via defaultTrackBinding). Each keyboard's MIDI channel comes from
         rig_config.json's "midiChannel" (1-indexed) or, if absent,
         auto-assigned to the next channel not already claimed by ch5
         (aux)/ch6 (stems)/ch7 (FX returns)/ch10 (pads)/ch16 (transport) —
         KBD1-4 default to ch1-4, same as before. (CC7 volume added
         2026-07-01 — previously Cmd+M-dependent, same gap as stems below.)
  ch6    CC1..N=vol, N+1..2N=mute, 2N+1..3N=solo → Stem tracks (N = stem
         count). (CC1..N volume added 2026-07-01, same reason as KBD above.)
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
# Loops), 5=CH6 stems, 6=CH7 FX returns, 9=CH10 pads, 14=CH15 Blue Hand
# (see below), 15=CH16 transport.
# Keyboards beyond the first 4 get the next free channel in that order
# unless rig_config.json specifies an explicit 1-indexed "midiChannel".
# Mirrors kbdDefaultChannel()/kbdChannel() in live_rig_3_controller.html --
# keep both in sync if the reserved set ever changes.
_RESERVED_KBD_CHANNELS_0IDX = (4, 5, 6, 9, 14, 15)

# ── Blue Hand mode (2026-06-30) ─────────────────────────────────────────────
# A global toggle (not a per-keyboard setting): while active for a given KBD
# slot, that slot's 8 faders stop reflecting their fixed defaultTrackBinding
# and instead directly drive whatever track is currently selected in Live --
# specifically its first device's first 8 parameters (any device, not just
# Racks, since this bypasses Ableton's own Cmd+M map entirely instead of
# risking cross-talk with it). Dedicated channel so it never collides with
# a KBD slot's normal Cmd+M-mapped fader CCs.
BLUE_HAND_CHANNEL_0IDX = 14  # CH15


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
SX_BLUE_HAND_ON    = 0x50   # value: kbd_idx to bind to the selected track
SX_BLUE_HAND_OFF   = 0x51   # value: kbd_idx (informational only)
SX_CLIP_FIRE       = 0x52   # value: (scene_idx<<3)|track_idx
SX_CLIP_STOP_TRACK = 0x53   # value: track_idx
SX_CLIP_STOP_ALL   = 0x54   # value: unused

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
FB_KBD_DEVICE      = 0x43   # data: kbd_idx, name length, name bytes, bank_idx, bank_count
FB_KBD_COLOR       = 0x44
FB_KBD_NAME        = 0x45
FB_STEM_COLOR      = 0x46
FB_STEM_NAME       = 0x47
FB_LOOP_STATE      = 0x48
FB_LOOP_QUANT      = 0x49   # data: loop_idx, quant_idx
FB_CLIP_TRACK_NAME = 0x50   # data: track_idx, name length, name bytes
FB_CLIP_INFO       = 0x51   # data: scene_idx, track_idx, flags, name length, name bytes
                             # flags: bit0=has_clip bit1=playing bit2=triggered bit3=recording
FB_KBD_VOLUME      = 0x52   # data: kbd_idx, v14_hi, v14_lo
FB_STEM_VOLUME     = 0x53   # data: stem_idx, v14_hi, v14_lo
FB_RETURN_VOLUME   = 0x54   # data: return_idx (0-3 = REV1/REV2/DLY1/DLY2), v14_hi, v14_lo
FB_AUX_VOLUME      = 0x55   # data: aux_idx (0=Click,1=Guide per rig_config "aux"), v14_hi, v14_lo
FB_BINDING_STATUS  = 0x56   # data: category, idx, status (see BIND_CAT_*/BIND_STATUS_* below)

# ── Track-binding status (2026-07-01) ───────────────────────────────────────
# rig_config.json binds KBD/stem/looper/aux slots to Ableton tracks by NAME
# (the only thing that persists in a .als file across a process restart or a
# duplicated Live Set -- Extensions SDK Handles are session-scoped and can't
# be saved into a config; see ONBOARDING.md). Name matching can go wrong in
# ways that used to be visible only in Log.txt: no track with that name
# exists anymore (renamed/deleted), or -- since Ableton allows two tracks to
# share a name -- more than one track matches and the first one silently
# wins. FB_BINDING_STATUS surfaces exactly which of these happened per slot
# so the iPad can show a visible indicator instead of a fader just quietly
# doing nothing.
BIND_CAT_KBD    = 0
BIND_CAT_STEM   = 1
BIND_CAT_LOOPER = 2
BIND_CAT_AUX    = 3

BIND_STATUS_OK               = 0  # resolved to exactly one matching track
BIND_STATUS_OK_POSITIONAL    = 1  # KBD only: no name configured, using position by design (normal)
BIND_STATUS_UNBOUND          = 2  # a binding was configured but nothing matches, and there's no fallback
BIND_STATUS_AMBIGUOUS        = 3  # 2+ tracks share the configured name; using the first (likely a mistake)
BIND_STATUS_EMPTY            = 4  # stems/loopers/aux only: deliberately unconfigured (trackName null)
BIND_STATUS_FALLBACK_MISMATCH = 5  # a name/index was configured but didn't match; silently fell back to
                                    # position (KBD only) -- almost always a real problem, e.g. a renamed track

# ── Clips page Session View grid (2026-07-01) ───────────────────────────────
# Mirrors the first CLIP_TRACKS tracks x CLIP_SCENES scenes of the actual
# Live set so the iPad's Clips page can show real clip names instead of
# generic "Track 1"/empty tiles. Positional (first 8 tracks/scenes), not
# name-bound like KBD/stems -- this is meant to mirror whatever's currently
# in Session View, not a fixed rig role.
# Polled rather than listener-driven, matching this file's existing
# precedent for frequently-changing state (see current_song_time note in
# the module docstring / _poll_song_time_tick) -- clip add/remove/rename/
# play state changes are simpler and more robust to poll at ~1s than to
# wire through Clip object listeners whose lifecycle churns every time a
# clip is dropped in or deleted.
CLIP_TRACKS  = 8
CLIP_SCENES  = 8

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

        # Aux tracks (Click/Guide on the Master page, CH5/index 4): named
        # tracks like stems, but historically had NO rig_config entry at
        # all, so both mute/solo and volume were 100% Cmd+M-dependent (the
        # gap David hit 2026-07-01 alongside the KBD/stem volume bug).
        # Deliberately opt-in: if rig_config.json has no "aux" list (or it's
        # empty), self._aux_count stays 0 and build_midi_map() never
        # registers ch5's CCs, so today's Cmd+M mapping keeps working
        # unchanged until real track names are added. Fixed CC scheme
        # (not dynamic like stems) matching the two hardcoded Master-page
        # columns in live_rig_3_controller.html: aux index 0 (Click) =
        # vol CC20/mute CC24/solo CC28, index 1 (Guide) = CC21/25/29.
        aux = rig_config.get("aux") or []
        self._aux_count = len(aux)
        self._aux_track_bindings = [a.get("trackName") for a in aux]
        self._aux_labels = [a.get("label") for a in aux]

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

        # Binding-status diff cache -- must exist before ANY _resolve_*_track_index
        # call below, since each one reports through _note_binding_status().
        self._binding_status_cache = {}

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

        # Blue Hand mode: None when off, else the KBD slot index whose faders
        # are currently mirroring/driving the selected track's first device.
        self._blue_hand_kbd_idx = None
        self._blue_hand_listeners = []

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

        # Volume feedback listeners (2026-07-01): KBD, stems, FX returns,
        # and (if configured) aux/Click-Guide -- so moving a fader by mouse
        # or automation in Ableton updates the corresponding iPad fader.
        self._kbd_volume_listeners = []
        self._stem_volume_listeners = []
        self._return_volume_listeners = []
        self._aux_volume_listeners = []
        try: self._rebind_kbd_volume_listeners()
        except Exception as e: self.log_message("rebind_kbd_volume init: " + str(e))
        try: self._emit_all_kbd_volumes()
        except Exception as e: self.log_message("emit_all_kbd_volumes init: " + str(e))
        try: self._rebind_stem_volume_listeners()
        except Exception as e: self.log_message("rebind_stem_volume init: " + str(e))
        try: self._emit_all_stem_volumes()
        except Exception as e: self.log_message("emit_all_stem_volumes init: " + str(e))
        try: self._rebind_return_volume_listeners()
        except Exception as e: self.log_message("rebind_return_volume init: " + str(e))
        try: self._emit_all_return_volumes()
        except Exception as e: self.log_message("emit_all_return_volumes init: " + str(e))
        try: self._rebind_aux_volume_listeners()
        except Exception as e: self.log_message("rebind_aux_volume init: " + str(e))
        try: self._emit_all_aux_volumes()
        except Exception as e: self.log_message("emit_all_aux_volumes init: " + str(e))

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

        # ~3.3 Hz Clips page Session View grid poll (see CLIP_TRACKS/CLIP_SCENES
        # comment above for why this is polled instead of listener-driven).
        # Tightened from the original ~1 Hz now that this page directly fires
        # clips -- a fired/triggered (blinking) state needs to show up quickly
        # after a tap, not up to a second later.
        self._clip_track_names_sent = [None] * CLIP_TRACKS
        self._clip_info_sent = {}
        self._clip_poll_active = True
        try:
            self.schedule_message(3, self._poll_clip_grid_tick)
        except Exception as e:
            self.log_message("clip grid schedule_message init: " + str(e))

    def disconnect(self):
        self._song_time_poll_active = False
        self._clip_poll_active = False
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
        try: self._unbind_blue_hand_listeners()
        except Exception: pass
        try: self._unbind_kbd_color_listeners()
        except Exception: pass
        try: self._unbind_kbd_name_listeners()
        except Exception: pass
        try: self._unbind_stem_color_listeners()
        except Exception: pass
        try: self._unbind_stem_name_listeners()
        except Exception: pass
        try: self._unbind_kbd_volume_listeners()
        except Exception: pass
        try: self._unbind_stem_volume_listeners()
        except Exception: pass
        try: self._unbind_return_volume_listeners()
        except Exception: pass
        try: self._unbind_aux_volume_listeners()
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

    def _poll_clip_grid_tick(self):
        """Re-schedule self every 3 ticks (~300ms). Diffs the first
        CLIP_TRACKS x CLIP_SCENES grid against what was last sent and only
        emits SysEx for cells that actually changed (name, has_clip,
        playing, triggered, or recording), so an idle Clips page generates
        zero MIDI traffic."""
        if not getattr(self, "_clip_poll_active", False):
            return
        try:
            self._scan_clip_grid()
        except Exception as e:
            self.log_message("clip grid poll error: " + str(e))
        self.schedule_message(3, self._poll_clip_grid_tick)

    def _scan_clip_grid(self, force=False):
        """force=True (used by _emit_full_state, e.g. on iPad reconnect)
        re-sends every cell regardless of the diff cache -- otherwise a
        freshly (re)connected iPad would see nothing until something in
        Live actually changes, since the cache still holds the last-sent
        values from before the reconnect.

        Play/trigger state is read from Track.playing_slot_index and
        Track.fired_slot_index (one int each per track, per the Live Object
        Model docs) rather than walking every clip's is_playing -- this
        mirrors exactly what Ableton's own Session View grid shows:
          playing_slot_index == si            -> that slot is playing (green)
          fired_slot_index == si and not
              already playing                 -> triggered/queued (blinking)
          neither, but has_clip                -> stopped (has a clip, idle)
          no clip                              -> empty
        `is_recording` still needs a per-clip read (Clip.is_recording), but
        only for the ONE slot that's actually playing on that track, since
        only one clip per track can be active at a time.
        """
        tracks = list(self.song().tracks)[:CLIP_TRACKS]
        for ti in range(CLIP_TRACKS):
            track = tracks[ti] if ti < len(tracks) else None
            name = track.name if track is not None else None
            if force or self._clip_track_names_sent[ti] != name:
                self._clip_track_names_sent[ti] = name
                self._emit_clip_track_name(ti, name)
            if track is None:
                continue
            try:
                playing_slot = track.playing_slot_index
            except Exception:
                playing_slot = -1
            try:
                fired_slot = track.fired_slot_index
            except Exception:
                fired_slot = -1
            slots = list(track.clip_slots)[:CLIP_SCENES]
            for si in range(CLIP_SCENES):
                if si >= len(slots):
                    continue
                slot = slots[si]
                has_clip = bool(slot.has_clip)
                clip_name = ""
                is_playing = False
                is_recording = False
                if has_clip:
                    try:
                        clip = slot.clip
                        clip_name = clip.name or ""
                    except Exception:
                        clip = None
                    if playing_slot == si:
                        is_playing = True
                        try:
                            is_recording = bool(clip.is_recording) if clip is not None else False
                        except Exception:
                            pass
                is_triggered = (fired_slot == si) and not is_playing
                key = (si, ti)
                snapshot = (has_clip, clip_name, is_playing, is_triggered, is_recording)
                if force or self._clip_info_sent.get(key) != snapshot:
                    self._clip_info_sent[key] = snapshot
                    self._emit_clip_info(si, ti, has_clip, clip_name, is_playing, is_triggered, is_recording)

    def _emit_clip_track_name(self, track_idx, name):
        try:
            body = [FB_CLIP_TRACK_NAME, track_idx & 0x7F]
            body += self._encode_str(name or "")
            self._send_sx(body)
        except Exception as e:
            self.log_message("clip track name emit error: " + str(e))

    def _emit_clip_info(self, scene_idx, track_idx, has_clip, clip_name, is_playing, is_triggered=False, is_recording=False):
        try:
            flags = 0
            if has_clip: flags |= 0x1
            if is_playing: flags |= 0x2
            if is_triggered: flags |= 0x4
            if is_recording: flags |= 0x8
            body = [FB_CLIP_INFO, scene_idx & 0x7F, track_idx & 0x7F, flags & 0x7F]
            body += self._encode_str(clip_name or "")
            self._send_sx(body)
        except Exception as e:
            self.log_message("clip info emit error: " + str(e))

    # ── Direct clip control (Session View, native Live Object Model) ────────
    def _clip_fire(self, scene_idx, track_idx):
        """Fire the clip slot at (scene_idx, track_idx) directly -- same
        effect as clicking it in Ableton: launches a clip, or if the slot
        is empty on an armed track, starts recording (matches ClipSlot.fire()
        semantics exactly, no special-casing needed here)."""
        try:
            tracks = list(self.song().tracks)[:CLIP_TRACKS]
            if track_idx >= len(tracks):
                self.log_message("clip fire: track_idx %d out of range" % track_idx)
                return
            slots = list(tracks[track_idx].clip_slots)[:CLIP_SCENES]
            if scene_idx >= len(slots):
                self.log_message("clip fire: scene_idx %d out of range" % scene_idx)
                return
            slots[scene_idx].fire()
        except Exception as e:
            self.log_message("clip fire error: " + str(e))

    def _clip_stop_track(self, track_idx):
        """Stop all playing/fired clips on one track -- Track.stop_all_clips()."""
        try:
            tracks = list(self.song().tracks)[:CLIP_TRACKS]
            if track_idx >= len(tracks):
                self.log_message("clip stop track: track_idx %d out of range" % track_idx)
                return
            tracks[track_idx].stop_all_clips()
        except Exception as e:
            self.log_message("clip stop track error: " + str(e))

    def _clip_stop_all(self):
        """Stop every playing/fired clip across the whole Live Set --
        Song.stop_all_clips(). Quantized (default) so it respects Global
        Quantization, same as the Stop Clips button in Ableton's own UI."""
        try:
            self.song().stop_all_clips()
        except Exception as e:
            self.log_message("clip stop all error: " + str(e))

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
        # Blue Hand: re-target to the newly-selected track's first device
        # without waiting for the iPad to resend SX_BLUE_HAND_ON.
        if self._blue_hand_kbd_idx is not None:
            self._rebind_blue_hand_listeners()

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
        self._rebind_kbd_volume_listeners()
        self._emit_all_kbd_volumes()
        self._rebind_stem_volume_listeners()
        self._emit_all_stem_volumes()
        self._rebind_return_volume_listeners()
        self._emit_all_return_volumes()
        self._rebind_aux_volume_listeners()
        self._emit_all_aux_volumes()
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

        Returns (index_or_None, status) -- status is one of the BIND_STATUS_*
        constants (2026-07-01, added so unresolved/ambiguous bindings can be
        surfaced on the iPad instead of only logged to Log.txt). The
        distinction that matters most: BIND_STATUS_OK_POSITIONAL means "no
        name was ever configured, using position by design" (normal, not an
        error) vs. BIND_STATUS_FALLBACK_MISMATCH, which means "a name WAS
        configured but doesn't match anything anymore, silently fell back to
        position" (almost certainly a real problem -- e.g. a track got
        renamed -- that used to be invisible outside Log.txt).
        """
        tracks = self.song().tracks
        def clamped_fallback():
            if fallback_idx is not None and 0 <= fallback_idx < len(tracks):
                return fallback_idx
            return None
        if binding is None:
            result = clamped_fallback()
            status = BIND_STATUS_OK_POSITIONAL if result is not None else BIND_STATUS_EMPTY
            self.log_message("%s resolve: unbound, fallback -> %s" % (label, result))
            return result, status
        if isinstance(binding, (int, float)):
            idx = int(binding)
            if 0 <= idx < len(tracks):
                self.log_message("%s resolve: index binding %s -> %s" % (label, idx, idx))
                return idx, BIND_STATUS_OK
            result = clamped_fallback()
            status = BIND_STATUS_FALLBACK_MISMATCH if result is not None else BIND_STATUS_UNBOUND
            self.log_message("%s resolve: index binding %s out of range -> fallback %s" % (label, idx, result))
            return result, status
        # String: case-insensitive name match -- collect ALL matches (not just
        # the first) so a duplicate track name can be flagged as ambiguous
        # instead of silently picking whichever happens to come first.
        name = str(binding).strip().lower()
        matches = []
        for idx, track in enumerate(tracks):
            try:
                if (track.name or "").strip().lower() == name:
                    matches.append(idx)
            except Exception:
                continue
        if len(matches) == 1:
            self.log_message("%s resolve: name '%s' matched track %d ('%s')" % (label, binding, matches[0], tracks[matches[0]].name))
            return matches[0], BIND_STATUS_OK
        if len(matches) > 1:
            self.log_message("%s resolve: name '%s' AMBIGUOUS -- %d tracks share this name (indices %s), using first" % (label, binding, len(matches), matches))
            return matches[0], BIND_STATUS_AMBIGUOUS
        # No match — fall back, preserving old KBD positional behavior
        result = clamped_fallback()
        all_names = [getattr(t, "name", "?") for t in tracks]
        self.log_message("%s resolve: name '%s' NOT FOUND among tracks %s -> fallback %s" % (label, binding, all_names, result))
        status = BIND_STATUS_FALLBACK_MISMATCH if result is not None else BIND_STATUS_UNBOUND
        return result, status

    def _note_binding_status(self, category, idx, status):
        """Cache+diff wrapper -- only emits FB_BINDING_STATUS when a given
        (category, idx)'s status actually changed, same diff-cache pattern
        already used for the clip grid. See _emit_all_binding_statuses for
        the force=True full-resend path (iPad reconnect)."""
        key = (category, idx)
        if self._binding_status_cache.get(key) != status:
            self._binding_status_cache[key] = status
            try:
                self._send_sx([FB_BINDING_STATUS, category & 0x7F, idx & 0x7F, status & 0x7F])
            except Exception as e:
                self.log_message("binding status emit error: " + str(e))

    def _resolve_kbd_track_index(self, ti):
        """Resolve KBD slot `ti` (0-3) to an actual track index, using
        rig_config's defaultTrackBinding. Falls back to the old positional
        behavior (track index == KBD slot) if unbound or no match is found,
        so sets that don't use defaultTrackBinding keep working unchanged.
        """
        binding = self._track_bindings[ti] if ti < len(self._track_bindings) else None
        idx, status = self._resolve_track_binding(binding, "kbd%d" % ti, fallback_idx=ti)
        self._note_binding_status(BIND_CAT_KBD, ti, status)
        return idx

    def _resolve_stem_track_index(self, si):
        """Resolve stem slot `si` to an actual track index, using rig_config's
        stems[si].trackName. No positional fallback -- stems are a distinct
        list with no natural correspondence to track order, so an unbound or
        unmatched stem just resolves to None (skipped) instead of guessing.
        """
        binding = self._stem_track_bindings[si] if si < len(self._stem_track_bindings) else None
        idx, status = self._resolve_track_binding(binding, "stem%d" % si, fallback_idx=None)
        self._note_binding_status(BIND_CAT_STEM, si, status)
        return idx

    def _resolve_aux_track_index(self, ai):
        """Resolve aux slot `ai` (0=Click, 1=Guide by rig_config.json order)
        to an actual track index, via rig_config's aux[ai].trackName. No
        positional fallback -- same reasoning as stems/loopers."""
        binding = self._aux_track_bindings[ai] if ai < len(self._aux_track_bindings) else None
        idx, status = self._resolve_track_binding(binding, "aux%d" % ai, fallback_idx=None)
        self._note_binding_status(BIND_CAT_AUX, ai, status)
        return idx

    def _resolve_looper_track_index(self, li):
        """Resolve loop slot `li` to an actual track index, using
        rig_config's loopers[li].trackName. No positional fallback -- loop
        tracks are dedicated and have no natural correspondence to KBD/stem
        order, so an unbound or unmatched loop slot just resolves to None
        (skipped) instead of guessing.
        """
        binding = self._looper_track_bindings[li] if li < len(self._looper_track_bindings) else None
        idx, status = self._resolve_track_binding(binding, "loop%d" % li, fallback_idx=None)
        self._note_binding_status(BIND_CAT_LOOPER, li, status)
        return idx

    def _emit_all_binding_statuses(self, force=False):
        """Re-resolve every configured binding across all 4 categories,
        which as a side effect (via _note_binding_status inside each
        _resolve_*_track_index above) emits any status that's changed.
        force=True clears the diff cache first so a freshly (re)connected
        iPad gets a full dump instead of nothing (mirrors _scan_clip_grid's
        force=True on _emit_full_state)."""
        if force:
            self._binding_status_cache = {}
        for ti in range(self._kbd_count):
            self._resolve_kbd_track_index(ti)
        for si in range(self._stem_count):
            self._resolve_stem_track_index(si)
        for li in range(self._looper_count):
            self._resolve_looper_track_index(li)
        for ai in range(self._aux_count):
            self._resolve_aux_track_index(ai)

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
                    self._emit_kbd_device(ti, None)
                    continue
                track = self.song().tracks[track_idx]
                device = self._find_first_device(track)
                self._emit_kbd_device(ti, device)  # header shows device name (or clears) either way
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

    # ── Blue Hand mode: KBD slot follows the selected track (any device) ────
    def _select_blue_hand_params(self, device):
        """First 8 parameters (after Device On) of ANY device -- unlike
        _select_macro_params, not restricted to Racks. Safe to do for any
        device here because Blue Hand is a dedicated channel this script
        drives directly (see build_midi_map/_dispatch_cc), not something
        layered on top of the user's own Cmd+M mappings."""
        try:
            params = device.parameters
        except Exception:
            return []
        return list(enumerate(params[1:9]))

    def _rebind_blue_hand_listeners(self):
        """(Re)bind Blue Hand feedback listeners to the selected track's
        first device. No-op if Blue Hand is off (self._blue_hand_kbd_idx is
        None). Called on SX_BLUE_HAND_ON and again whenever the selected
        track changes while active, so it always follows live."""
        self._unbind_blue_hand_listeners()
        if self._blue_hand_kbd_idx is None:
            return
        kbd_idx = self._blue_hand_kbd_idx
        try:
            sel = self.song().view.selected_track
            if sel is None:
                self.log_message("blue hand bind: no track selected")
                self._emit_kbd_device(kbd_idx, None)
                return
            device = self._find_first_device(sel)
            self._emit_kbd_device(kbd_idx, device)  # header shows what Blue Hand is now driving
            if device is None:
                self.log_message("blue hand bind: '%s' has no devices" % getattr(sel, "name", "?"))
                return
            bound_count = 0
            for param_idx, param in self._select_blue_hand_params(device):
                listener = lambda p=param, k=kbd_idx, i=param_idx: self._emit_macro_value(k, i, p)
                param.add_value_listener(listener)
                self._blue_hand_listeners.append((param, listener))
                self._emit_macro_value(kbd_idx, param_idx, param)  # push current value immediately
                bound_count += 1
            self.log_message("blue hand bind: kbd%d -> track '%s' device '%s', %d params" % (
                kbd_idx, getattr(sel, "name", "?"), getattr(device, "name", "?"), bound_count))
        except Exception as e:
            self.log_message("blue hand bind error: " + str(e))

    def _unbind_blue_hand_listeners(self):
        for param, listener in self._blue_hand_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._blue_hand_listeners = []

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

    # ── Volume feedback listeners (2026-07-01): Ableton -> iPad ─────────────
    # Mirrors color/name listeners above, but for mixer_device.volume, so
    # moving a fader with the mouse in Live (or via automation) keeps the
    # Master/Stems fader on the iPad in sync -- these are the same tracks
    # CC7/stem-CC1..N/aux-CC20-21/FX-return-CC1-4 already control directly
    # (see build_midi_map/_dispatch_cc), just the missing feedback half.
    def _rebind_kbd_volume_listeners(self):
        self._unbind_kbd_volume_listeners()
        try:
            for ti in range(self._kbd_count):
                track_idx = self._resolve_kbd_track_index(ti)
                if track_idx is None:
                    continue
                vol_param = self.song().tracks[track_idx].mixer_device.volume
                kbd_idx = ti
                listener = lambda t=kbd_idx: self._emit_kbd_volume(t)
                vol_param.add_value_listener(listener)
                self._kbd_volume_listeners.append((vol_param, listener))
        except Exception as e:
            self.log_message("rebind kbd volume error: " + str(e))

    def _unbind_kbd_volume_listeners(self):
        for param, listener in self._kbd_volume_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._kbd_volume_listeners = []

    def _emit_kbd_volume(self, ti):
        try:
            track_idx = self._resolve_kbd_track_index(ti)
            if track_idx is None:
                return
            vol = self.song().tracks[track_idx].mixer_device.volume.value
            v14 = int(round(max(0.0, min(1.0, vol)) * 0x3FFF))
            self._send_sx([FB_KBD_VOLUME, ti & 0x7F] + self._encode_uint14(v14))
        except Exception as e:
            self.log_message("kbd volume emit error: " + str(e))

    def _emit_all_kbd_volumes(self):
        for ti in range(self._kbd_count):
            self._emit_kbd_volume(ti)

    def _rebind_stem_volume_listeners(self):
        self._unbind_stem_volume_listeners()
        try:
            for si in range(self._stem_count):
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is None:
                    continue
                vol_param = self.song().tracks[track_idx].mixer_device.volume
                stem_idx = si
                listener = lambda t=stem_idx: self._emit_stem_volume(t)
                vol_param.add_value_listener(listener)
                self._stem_volume_listeners.append((vol_param, listener))
        except Exception as e:
            self.log_message("rebind stem volume error: " + str(e))

    def _unbind_stem_volume_listeners(self):
        for param, listener in self._stem_volume_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._stem_volume_listeners = []

    def _emit_stem_volume(self, si):
        try:
            track_idx = self._resolve_stem_track_index(si)
            if track_idx is None:
                return
            vol = self.song().tracks[track_idx].mixer_device.volume.value
            v14 = int(round(max(0.0, min(1.0, vol)) * 0x3FFF))
            self._send_sx([FB_STEM_VOLUME, si & 0x7F] + self._encode_uint14(v14))
        except Exception as e:
            self.log_message("stem volume emit error: " + str(e))

    def _emit_all_stem_volumes(self):
        for si in range(self._stem_count):
            self._emit_stem_volume(si)

    def _rebind_return_volume_listeners(self):
        """FX Return tracks (REV1/REV2/DLY1/DLY2) aren't config-bound like
        KBD/stems -- fixed positional (song().return_tracks[0-3]), matching
        the existing _dispatch_cc handling for these same 4 channels."""
        self._unbind_return_volume_listeners()
        try:
            ret_tracks = list(self.song().return_tracks)[:4]
            for ri, track in enumerate(ret_tracks):
                vol_param = track.mixer_device.volume
                return_idx = ri
                listener = lambda t=return_idx: self._emit_return_volume(t)
                vol_param.add_value_listener(listener)
                self._return_volume_listeners.append((vol_param, listener))
        except Exception as e:
            self.log_message("rebind return volume error: " + str(e))

    def _unbind_return_volume_listeners(self):
        for param, listener in self._return_volume_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._return_volume_listeners = []

    def _emit_return_volume(self, ri):
        try:
            ret_tracks = list(self.song().return_tracks)
            if ri >= len(ret_tracks):
                return
            vol = ret_tracks[ri].mixer_device.volume.value
            v14 = int(round(max(0.0, min(1.0, vol)) * 0x3FFF))
            self._send_sx([FB_RETURN_VOLUME, ri & 0x7F] + self._encode_uint14(v14))
        except Exception as e:
            self.log_message("return volume emit error: " + str(e))

    def _emit_all_return_volumes(self):
        for ri in range(4):
            self._emit_return_volume(ri)

    def _rebind_aux_volume_listeners(self):
        """No-op if self._aux_count == 0 (no rig_config 'aux' section yet
        -- see __init__ comment); becomes active as soon as real Click/Guide
        track names are added, no other code changes needed."""
        self._unbind_aux_volume_listeners()
        try:
            for ai in range(self._aux_count):
                track_idx = self._resolve_aux_track_index(ai)
                if track_idx is None:
                    continue
                vol_param = self.song().tracks[track_idx].mixer_device.volume
                aux_idx = ai
                listener = lambda t=aux_idx: self._emit_aux_volume(t)
                vol_param.add_value_listener(listener)
                self._aux_volume_listeners.append((vol_param, listener))
        except Exception as e:
            self.log_message("rebind aux volume error: " + str(e))

    def _unbind_aux_volume_listeners(self):
        for param, listener in self._aux_volume_listeners:
            try:
                param.remove_value_listener(listener)
            except Exception:
                pass
        self._aux_volume_listeners = []

    def _emit_aux_volume(self, ai):
        try:
            track_idx = self._resolve_aux_track_index(ai)
            if track_idx is None:
                return
            vol = self.song().tracks[track_idx].mixer_device.volume.value
            v14 = int(round(max(0.0, min(1.0, vol)) * 0x3FFF))
            self._send_sx([FB_AUX_VOLUME, ai & 0x7F] + self._encode_uint14(v14))
        except Exception as e:
            self.log_message("aux volume emit error: " + str(e))

    def _emit_all_aux_volumes(self):
        for ai in range(self._aux_count):
            self._emit_aux_volume(ai)

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
          KBD vol/mute/solo — CC7=volume, CC1=mute, CC2=solo on each
                           keyboard's MIDI channel (dynamic, self._kbd_channels
                           -- was hardcoded ch1-4). CC7 volume added
                           2026-07-01 -- previously only mute/solo were
                           direct-CC, so the Master page's KBD volume
                           faders silently depended on the user manually
                           Cmd+M-mapping CC7 to each track's mixer volume
                           in Ableton, which is fragile/easy to lose
                           (new Live Set, Remote Script re-init, etc).
          Stem vol/mute/solo — CC1..N=volume, N+1..2N=mute, 2N+1..3N=solo on
                           MIDI ch6 (dynamic per STEM_COUNT). Volume (1..N)
                           added 2026-07-01 for the same reason as KBD above.
          FX returns     — CC1-12 on MIDI ch7      (vol + mute + solo)
          Aux (Click/Guide) — CC20/21=vol, CC24/25=mute, CC28/29=solo on
                           MIDI ch5 (index 4) -- ONLY if rig_config.json
                           defines an "aux" list (self._aux_count > 0).
                           Opt-in on purpose: with no aux config, these CCs
                           are left alone so any existing Cmd+M mapping in
                           Ableton keeps working exactly as before. Added
                           2026-07-01 alongside the KBD/stem volume fix.
          Blue Hand      — CC10-17 on MIDI ch15    (selected track's first
                           device's first 8 params; only acts when a KBD
                           slot has Blue Hand toggled on -- see _dispatch_cc)
        """
        # KBD volume (CC7), mute (CC1), solo (CC2) on each keyboard's
        # assigned channel -- all three now handled directly, no Cmd+M
        # mapping needed for any of them.
        for ch in self._kbd_channels:
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, ch, 1)
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, ch, 2)
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, ch, 7)
        # Stem volume (CC1..N) + mute/solo (CC N+1..3N) on MIDI ch6 (index 5)
        n = self._stem_count
        for cc in range(1, 3 * n + 1):
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, 5, cc)
        # FX Return vol+mute+solo on MIDI ch7 (index 6): CC1-12
        for cc in range(1, 13):
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, 6, cc)
        # Aux (Click/Guide) vol/mute/solo on MIDI ch5 (index 4) -- opt-in,
        # only registered if rig_config.json actually defines aux tracks
        # (see __init__/self._aux_count comment). Fixed CC scheme matching
        # the two hardcoded Master-page columns: CC20/24/28 = Click
        # vol/mute/solo, CC21/25/29 = Guide vol/mute/solo.
        if self._aux_count > 0:
            for ai in range(self._aux_count):
                Live.MidiMap.forward_midi_cc(
                    self._c_instance.handle(), midi_map_handle, 4, 20 + ai)
                Live.MidiMap.forward_midi_cc(
                    self._c_instance.handle(), midi_map_handle, 4, 24 + ai)
                Live.MidiMap.forward_midi_cc(
                    self._c_instance.handle(), midi_map_handle, 4, 28 + ai)
        # Blue Hand param control on its dedicated channel: CC10-17
        for cc in range(10, 18):
            Live.MidiMap.forward_midi_cc(
                self._c_instance.handle(), midi_map_handle, BLUE_HAND_CHANNEL_0IDX, cc)

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

        # ── KBD tracks: each keyboard's assigned channel, CC7=volume,
        # CC1=mute, CC2=solo ── (was hardcoded "0 <= channel <= 3" assuming
        # channel index == KBD slot; now resolved via
        # self._kbd_channel_to_index so KBD5+ on any free channel still
        # routes correctly.)
        if channel in self._kbd_channel_to_index and cc in (1, 2, 7):
            ti = self._kbd_channel_to_index[channel]
            track_idx = self._resolve_kbd_track_index(ti)
            if track_idx is None:
                return
            try:
                track = song.tracks[track_idx]
                if cc == 1:
                    track.mute = bool(val)
                elif cc == 2:
                    track.solo = bool(val)
                else:  # cc == 7: volume
                    track.mixer_device.volume.value = val / 127.0
            except Exception as e:
                self.log_message("kbd%d vol/mute/solo error: %s" % (ti, str(e)))
            return

        # ── Aux (Click/Guide): MIDI ch5 (index 4), volume/mute/solo ──────────
        # Only ever reaches here if self._aux_count > 0 (see build_midi_map --
        # otherwise these CCs are never registered/forwarded at all, so
        # Ableton's own Cmd+M mapping keeps handling them untouched).
        if channel == 4 and self._aux_count > 0:
            for ai in range(self._aux_count):
                track_idx = self._resolve_aux_track_index(ai)
                if track_idx is None:
                    continue
                if cc == 20 + ai:
                    try:
                        song.tracks[track_idx].mixer_device.volume.value = val / 127.0
                    except Exception:
                        pass
                elif cc == 24 + ai:
                    try:
                        song.tracks[track_idx].mute = bool(val)
                    except Exception:
                        pass
                elif cc == 28 + ai:
                    try:
                        song.tracks[track_idx].solo = bool(val)
                    except Exception:
                        pass
            return

        # ── Stems: MIDI ch6 (index 5), volume/mute/solo ──────────────────────
        if channel == 5:
            n = self._stem_count
            if n == 0:
                return
            # volume: CC1 .. N
            if 1 <= cc <= n:
                si = cc - 1
                track_idx = self._resolve_stem_track_index(si)
                if track_idx is not None:
                    try:
                        song.tracks[track_idx].mixer_device.volume.value = val / 127.0
                    except Exception:
                        pass
            # mutes:  CC N+1 .. 2N
            elif n + 1 <= cc <= 2 * n:
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

        # ── Blue Hand: dedicated channel, CC10-17 -> selected track's first
        # device's first 8 params directly (bypasses Cmd+M entirely). A no-op
        # whenever Blue Hand is off (self._blue_hand_kbd_idx is None) -- the
        # channel is always registered in build_midi_map so no rebuild is
        # needed when toggling, it just does nothing until a slot opts in.
        # Resolves the selected track fresh on every CC (not just via the
        # rebind-on-selection-change listener) so a fast track-then-fader
        # sequence can't land on a stale target.
        if channel == BLUE_HAND_CHANNEL_0IDX and 10 <= cc <= 17:
            if self._blue_hand_kbd_idx is None:
                return
            try:
                sel = song.view.selected_track
                if sel is None:
                    return
                device = self._find_first_device(sel)
                if device is None:
                    return
                params = device.parameters[1:9]
                pi = cc - 10
                if pi >= len(params):
                    return
                param = params[pi]
                pmin, pmax = param.min, param.max
                param.value = pmin + (val / 127.0) * (pmax - pmin)
            except Exception as e:
                self.log_message("blue hand cc error: %s" % str(e))
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
        elif code == SX_BLUE_HAND_ON:
            self.log_message("dispatch: SX_BLUE_HAND_ON kbd=%s" % value)
            # Pause ALL normal KBD macro feedback while Blue Hand is active,
            # not just the affected slot -- avoids two listeners racing to
            # update the same kbd_idx's fader if the fixed-track binding's
            # own macro happened to change at the same moment.
            self._unbind_macro_listeners()
            self._blue_hand_kbd_idx = value
            self._rebind_blue_hand_listeners()
        elif code == SX_BLUE_HAND_OFF:
            self.log_message("dispatch: SX_BLUE_HAND_OFF kbd=%s" % value)
            self._blue_hand_kbd_idx = None
            self._unbind_blue_hand_listeners()
            self._rebind_macro_listeners()  # restores normal feedback + device headers for all KBD slots
        elif code == SX_CLIP_FIRE:
            scene_idx = (value >> 3) & 0x0F
            track_idx = value & 0x07
            self.log_message("dispatch: SX_CLIP_FIRE scene=%s track=%s" % (scene_idx, track_idx))
            self._clip_fire(scene_idx, track_idx)
        elif code == SX_CLIP_STOP_TRACK:
            self.log_message("dispatch: SX_CLIP_STOP_TRACK track=%s" % value)
            self._clip_stop_track(value)
        elif code == SX_CLIP_STOP_ALL:
            self.log_message("dispatch: SX_CLIP_STOP_ALL")
            self._clip_stop_all()

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

    def _emit_kbd_device(self, kbd_idx, device):
        """Tells the iPad which device (if any) a KBD slot's faders are
        currently bound to, so the page header can show it instead of
        leaving the user guessing. `device` may be None (no devices on the
        bound track) -- sends an empty name so a stale header gets cleared.
        No bank/paging concept exists yet, so bank_idx/bank_count are
        always 0/1 (the iPad only shows a "BANK x/y" suffix when >1)."""
        try:
            name = getattr(device, "name", "") if device is not None else ""
            body = [FB_KBD_DEVICE, kbd_idx & 0x7F]
            body += self._encode_str(name)
            body += [0, 1]
            self._send_sx(body)
        except Exception as e:
            self.log_message("kbd device emit error: " + str(e))

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
        self._emit_all_kbd_volumes()
        self._emit_all_stem_volumes()
        self._emit_all_return_volumes()
        self._emit_all_aux_volumes()
        self._emit_all_looper_states()
        self._emit_all_looper_quants()
        try:
            self._emit_all_binding_statuses(force=True)
        except Exception as e:
            self.log_message("binding status full-state emit error: " + str(e))
        try:
            self._scan_clip_grid(force=True)
        except Exception as e:
            self.log_message("clip grid full-state emit error: " + str(e))
