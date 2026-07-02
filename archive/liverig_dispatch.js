// liverig_dispatch.js — receives SysEx bytes from sysexin (one int per inlet message)
// Format: F0 7D <code> <value> F7  →  240 125 NN VV 247

inlets = 1;
outlets = 1;

var LIVERIG_MFG_ID = 125;
var sxBuffer = [];

function bang() {}
function anything() {}

function msg_int(v) {
    // Start of SysEx
    if (v === 240) {
        sxBuffer = [];
        return;
    }
    // End of SysEx — process buffer
    if (v === 247) {
        if (sxBuffer.length >= 2 && sxBuffer[0] === LIVERIG_MFG_ID) {
            var code  = sxBuffer[1] & 0x7F;
            var value = (sxBuffer.length >= 3) ? (sxBuffer[2] & 0x7F) : 0;
            post("liverig_dispatch: code=0x" + code.toString(16) + " val=" + value + "\n");
            dispatch(code, value);
        }
        sxBuffer = [];
        return;
    }
    // Middle bytes
    sxBuffer.push(v & 0x7F);
}

// Also support list-style emission (some Max versions/objects send the whole frame at once)
function list() {
    var args = arrayfromargs(arguments);
    var bytes = [];
    for (var i = 0; i < args.length; i++) {
        if (args[i] === 240 || args[i] === 247) continue;
        bytes.push(args[i] & 0x7F);
    }
    if (bytes.length < 2 || bytes[0] !== LIVERIG_MFG_ID) return;
    var code  = bytes[1];
    var value = (bytes.length >= 3) ? bytes[2] : 0;
    post("liverig_dispatch (list): code=0x" + code.toString(16) + " val=" + value + "\n");
    dispatch(code, value);
}

function dispatch(code, value) {
    try {
        var song = new LiveAPI("live_set");
        switch (code) {
            // ── MARKERS ──
            case 0x30: // locator_jump (value = index, 0-127)
                var cuePts = song.get("cue_points");
                if (cuePts && value < cuePts.length / 2) {
                    var cue = new LiveAPI("live_set cue_points " + value);
                    cue.call("jump");
                }
                return;
            case 0x31: // next marker
                song.call("jump_to_next_cue");
                return;
            case 0x32: // prev marker
                song.call("jump_to_prev_cue");
                return;
            case 0x33: // scene fire (value = scene index)
                try {
                    var scene = new LiveAPI("live_set scenes " + value);
                    scene.call("fire");
                } catch(e2) { post("scene fire failed: " + e2.message + "\n"); }
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
        post("liverig_dispatch error code=0x" + code.toString(16) + ": " + e.message + "\n");
    }
}
