// liverig_send.js — v13 — throttled LiveAPI queries to prevent audio hiccups
// Inlets: 0=transport, 1=bar, 2=bpm, 3=timesig, 4=song_name, 5=unused, 6=beat, 7=song_time, 8=song_len

inlets = 9;
outlets = 1;

var state = {
    transport: "stopped",
    bar: 0,
    beat: 0,
    bpm: 120,
    timesig: 4,
    song: "",
    song_time: 0,
    song_len: 0,
    songs: [],
    sections: [],
    locators: [],
    current_song: "",
    current_section: "",
    tracks: [],
    clips: []
};

var lastSend = 0;
var lastCueRefresh = 0;    // cue points refresh every 3s
var lastSessionRefresh = 0; // tracks+clips every 3s
var sessionStep = 0;        // which track index to poll on next tick
var sessionWarned = false;
var sessionCache = { tracks: [], clips: [] };  // Build incrementally, swap when complete

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
    recomputeCurrent();
    writeFile();
}

function msg_float(v) {
    if (inlet === 2) state.bpm       = Math.round(v * 10) / 10;
    if (inlet === 7) state.song_time = Math.round(v * 1000) / 1000;
    if (inlet === 8) state.song_len  = Math.round(v * 1000) / 1000;
    recomputeCurrent();
    writeFile();
}

function msg_string(v) {
    if (inlet === 4) { state.song = v; writeFile(); }
}

function list() { /* inlet 5 unused */ }

function recomputeCurrent() {
    var t = state.song_time;
    var cs = "";
    for (var i = 0; i < state.songs.length; i++) {
        if (state.songs[i].time <= t) cs = state.songs[i].name;
    }
    state.current_song = cs;
    var sec = "";
    for (var j = 0; j < state.sections.length; j++) {
        if (state.sections[j].time <= t) sec = state.sections[j].name;
    }
    state.current_section = sec;
}

// Query cue points — runs every 3 seconds. Lightweight: just names + times.
function refreshCuePoints() {
    try {
        var liveSet = new LiveAPI("live_set");
        var cueCount = liveSet.getcount("cue_points");
        var raw = [], songs = [], sections = [];
        for (var c = 0; c < cueCount; c++) {
            var cue = new LiveAPI("live_set cue_points " + c);
            var nameArr = cue.get("name");
            var timeArr = cue.get("time");
            var nm = (nameArr && nameArr.length) ? String(nameArr[0]) : "";
            var tm = (timeArr && timeArr.length) ? Number(timeArr[0]) : 0;
            raw.push({ name: nm, time: tm });
            if (nm.toLowerCase().indexOf("song:") === 0) {
                songs.push({ name: nm.substring(5).replace(/^\s+/, ""), time: tm });
            } else if (nm.length) {
                sections.push({ name: nm, time: tm });
            }
        }
        raw.sort(function(a,b){ return a.time - b.time; });
        songs.sort(function(a,b){ return a.time - b.time; });
        sections.sort(function(a,b){ return a.time - b.time; });
        state.locators = raw;
        state.songs    = songs;
        state.sections = sections;
    } catch(e) {
        if (!sessionWarned) { post("liverig_send: cue query failed: " + e.message + "\n"); sessionWarned = true; }
    }
}

// Query ONE track's info + its clip slots — call incrementally, one per tick.
function refreshOneTrack(ti) {
    try {
        var liveSet = new LiveAPI("live_set");
        var trackCount = liveSet.getcount("tracks");
        if (ti >= trackCount) return;

        var track = new LiveAPI("live_set tracks " + ti);
        var tname = track.get("name");
        tname = (tname && tname.length) ? String(tname[0]) : ("Track " + (ti+1));
        var muteArr = track.get("mute");
        var soloArr = track.get("solo");
        sessionCache.tracks[ti] = {
            name: tname,
            mute: (muteArr && muteArr.length) ? muteArr[0] : 0,
            solo: (soloArr && soloArr.length) ? soloArr[0] : 0
        };

        var sceneCount = Math.min(liveSet.getcount("scenes"), 8);
        for (var si = 0; si < sceneCount; si++) {
            if (!sessionCache.clips[si]) sessionCache.clips[si] = [];
            var slot = new LiveAPI("live_set tracks " + ti + " clip_slots " + si);
            var hasClipArr = slot.get("has_clip");
            var isHas = (hasClipArr && hasClipArr.length) ? hasClipArr[0] : 0;
            var clipName = "";
            var playing = 0;
            if (isHas) {
                var clipApi = new LiveAPI("live_set tracks " + ti + " clip_slots " + si + " clip");
                var cn = clipApi.get("name");
                if (cn && cn.length) clipName = String(cn[0]);
                var isPlaying = slot.get("is_playing");
                playing = (isPlaying && isPlaying.length) ? isPlaying[0] : 0;
            }
            sessionCache.clips[si][ti] = { has: isHas, name: clipName, playing: playing };
        }
    } catch(e) {
        if (!sessionWarned) { post("liverig_send: track query failed: " + e.message + "\n"); sessionWarned = true; }
    }
}

function writeFile() {
    var now = Date.now();
    if (now - lastSend < 100) return;
    lastSend = now;

    // CUE POINTS every 3 seconds
    if (now - lastCueRefresh > 3000) {
        refreshCuePoints();
        recomputeCurrent();
        lastCueRefresh = now;
    }

    // TRACKS + CLIPS: stagger — one track per writeFile tick (every 100ms)
    // Total cycle: 8 tracks × 100ms = ~800ms for full refresh
    // After full cycle (idle for 2s), repeat
    if (now - lastSessionRefresh > 2000) {
        refreshOneTrack(sessionStep);
        sessionStep++;
        if (sessionStep >= 8) {
            // Completed one full cycle — swap cache into state and rest
            state.tracks = sessionCache.tracks.slice();
            state.clips  = sessionCache.clips.map(function(r){ return r.slice(); });
            sessionStep = 0;
            lastSessionRefresh = now;
        }
    }

    var json = JSON.stringify(state);
    outlet(0, json);

    try {
        var f = new File("/tmp/liverig_state.json", "write", "TEXT");
        if (f.isopen) {
            f.eof = 0;
            f.position = 0;
            f.writestring(json);
            f.close();
        }
    } catch(e) {}
}
