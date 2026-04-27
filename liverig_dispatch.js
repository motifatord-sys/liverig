// liverig_dispatch.js — handles incoming SysEx from the bridge and calls Live API
// Format: F0 7D <code> <value> F7 (sxformat strips F0/F7, gives us [125, code, value])

inlets = 1;
outlets = 1;

function bang() {}
function anything() {}

// Manufacturer ID 0x7D = 125 (educational/non-commercial)
var LIVERIG_MFG_ID = 125;

// Code → action lookup
function dispatch(code, value) {
    try {
        var song = new LiveAPI("live_set");
        switch (code) {
            // ── MARKERS ──
            case 0x30: // locator_jump (value = index, 0-127)
                var cuePts = song.get("cue_points");
                if (cuePts && value < cuePts.length / 2) {
                    var cuePath = "live_set cue_points " + value;
                    var cue = new LiveAPI(cuePath);
                    cue.call("jump");
                }
                return;
            case 0x31: // next marker
                song.call("jump_to_next_cue");
                return;
            case 0x32: // prev marker
                song.call("jump_to_prev_cue");
                return;

            // ── TRANSPORT ──
            case 0x40: // play
                song.call("start_playing");
                return;
            case 0x41: // stop
                song.call("stop_playing");
                return;
            case 0x42: // record toggle
                var rec = song.get("record_mode");
                song.set("record_mode", (rec && rec[0]) ? 0 : 1);
                return;
            case 0x43: // overdub toggle
                var od = song.get("overdub");
                song.set("overdub", (od && od[0]) ? 0 : 1);
                return;
            case 0x44: // metronome toggle
                var m = song.get("metronome");
                song.set("metronome", (m && m[0]) ? 0 : 1);
                return;
            case 0x45: // arrangement loop toggle
                var lp = song.get("loop");
                song.set("loop", (lp && lp[0]) ? 0 : 1);
                return;
            case 0x46: // punch in toggle
                var pi = song.get("punch_in");
                song.set("punch_in", (pi && pi[0]) ? 0 : 1);
                return;
            case 0x47: // tap tempo
                song.call("tap_tempo");
                return;
            case 0x48: // undo
                if (song.get("can_undo") && song.get("can_undo")[0]) song.call("undo");
                return;
            case 0x49: // redo
                if (song.get("can_redo") && song.get("can_redo")[0]) song.call("redo");
                return;
        }
    } catch (e) {
        post("liverig_dispatch error code=" + code + ": " + e.message + "\n");
    }
}

// Incoming list from midiparse outlet 6: may include F0 (240) and F7 (247) wrappers,
// or may be stripped — handle both shapes.
function list() {
    var args = arrayfromargs(arguments);
    if (args.length < 2) return;

    // Strip F0/F7 wrappers if present
    var bytes = [];
    for (var i = 0; i < args.length; i++) {
        if (args[i] === 240 || args[i] === 247) continue;
        bytes.push(args[i]);
    }
    if (bytes.length < 2) return;

    // First byte must be our manufacturer ID (0x7D = 125)
    if (bytes[0] !== LIVERIG_MFG_ID) return;
    var code  = bytes[1] & 0x7F;
    var value = (bytes.length >= 3) ? (bytes[2] & 0x7F) : 0;
    post("liverig_dispatch: code=0x" + code.toString(16) + " val=" + value + "\n");
    dispatch(code, value);
}