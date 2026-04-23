// liverig_send.js — v9 — correct File constructor usage per Max docs

inlets = 7;
outlets = 1;

var state = {
    transport: "stopped",
    bar: 0,
    beat: 0,
    bpm: 120,
    timesig: 4,
    song: "",
    locators: [],
    current_locator: ""
};

var lastSend = 0;
var writeCount = 0;
var writeErr = 0;

function bang() {}
function anything() {}

function stopped()   { state.transport = "stopped";   writeFile(); }
function playing()   { state.transport = "playing";   writeFile(); }
function recording() { state.transport = "recording"; writeFile(); }

function msg_int(v) {
    if (inlet === 1) state.bar     = v;
    if (inlet === 2) state.bpm     = v;
    if (inlet === 3) state.timesig = v;
    if (inlet === 6) state.beat    = v;
    writeFile();
}

function msg_float(v) {
    if (inlet === 2) state.bpm = Math.round(v * 10) / 10;
    writeFile();
}

function msg_string(v) {
    if (inlet === 4) { state.song = v; writeFile(); }
}

function list() {
    if (inlet === 5) {
        var args = arrayfromargs(arguments);
        state.locators = [];
        for (var i = 0; i + 1 < args.length; i += 2) {
            state.locators.push({ name: String(args[i]), bar: Number(args[i+1]) });
        }
        var cur = "";
        for (var j = 0; j < state.locators.length; j++) {
            if (state.locators[j].bar <= state.bar) cur = state.locators[j].name;
        }
        state.current_locator = cur;
        writeFile();
    }
}

function writeFile() {
    var now = Date.now();
    if (now - lastSend < 100) return;
    lastSend = now;

    var json = JSON.stringify(state);

    // Output to udpsend
    outlet(0, json);

    // Write to absolute path - pass as constructor argument
    try {
        var f = new File("/tmp/liverig_state.json", "write", "TEXT");
        if (f.isopen) {
            f.eof = 0;
            f.position = 0;
            f.writestring(json);
            f.close();
            writeCount++;
            if (writeCount === 1 || writeCount % 50 === 0) {
                post("liverig_send: wrote #" + writeCount + " → /tmp/liverig_state.json\n");
            }
        } else {
            writeErr++;
            if (writeErr < 5) {
                post("liverig_send: file not open, err#" + writeErr + "\n");
            }
        }
    } catch(e) {
        post("liverig_send: " + e.message + "\n");
    }
}
