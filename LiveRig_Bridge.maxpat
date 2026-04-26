{
	"patcher" : {
		"fileversion" : 1,
		"appversion" : { "major" : 8, "minor" : 6, "revision" : 0, "architecture" : "x64", "modernui" : 1 },
		"classnamespace" : "dsp.midi",
		"rect" : [ 50.0, 50.0, 1100.0, 780.0 ],
		"boxes" : [
			{ "box" : { "id" : "obj-title", "maxclass" : "comment", "numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 10.0, 1040.0, 20.0 ],
				"text" : "LiveRig Bridge v11 — adds live.observer for current_song_time (position) and last_event_time (song length). Smart locator split via liverig_send.js." } },

			{ "box" : { "id" : "obj-thisdevice", "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 30.0, 40.0, 120.0, 22.0 ], "text" : "live.thisdevice" } },
			{ "box" : { "id" : "obj-loadbang",   "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 170.0, 40.0, 80.0, 22.0 ],  "text" : "loadbang" } },
			{ "box" : { "id" : "obj-metro",       "maxclass" : "newobj", "numinlets" : 2, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 30.0, 75.0, 80.0, 22.0 ],   "text" : "metro 100" } },

			{ "box" : { "id" : "obj-transport", "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 9,
				"outlettype" : [ "int", "int", "int", "int", "float", "list", "int", "int", "list" ],
				"patching_rect" : [ 30.0, 110.0, 80.0, 22.0 ], "text" : "transport" } },

			{ "box" : { "id" : "obj-bar-int",   "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 30.0,  145.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-beat-int",  "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 80.0,  145.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-bpm-int",   "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 130.0, 145.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-tsig-zl",  "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 180.0, 145.0, 60.0, 22.0 ], "text" : "zl nth 1" } },
			{ "box" : { "id" : "obj-sel-state", "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 250.0, 145.0, 60.0, 22.0 ], "text" : "sel 0 1" } },
			{ "box" : { "id" : "obj-msg-stop",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 250.0, 175.0, 70.0, 22.0 ], "text" : "stopped" } },
			{ "box" : { "id" : "obj-msg-play",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 330.0, 175.0, 60.0, 22.0 ], "text" : "playing" } },

			{ "box" : { "id" : "obj-c-song", "maxclass" : "comment", "numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 400.0, 40.0, 650.0, 20.0 ],
				"text" : "live.path + live.object: song name. live.observer chains: current_song_time, last_event_time, cue_points" } },

			{ "box" : { "id" : "obj-lpath",    "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 400.0, 70.0, 120.0, 22.0 ],  "text" : "live.path" } },
			{ "box" : { "id" : "obj-lobj",     "maxclass" : "newobj","numinlets" : 2, "numoutlets" : 2, "patching_rect" : [ 400.0, 100.0, 120.0, 22.0 ], "text" : "live.object" } },
			{ "box" : { "id" : "obj-pathmsg",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 400.0, 40.0, 130.0, 22.0 ],  "text" : "path live_set" } },
			{ "box" : { "id" : "obj-getname",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 535.0, 100.0, 80.0, 22.0 ], "text" : "get name" } },
			{ "box" : { "id" : "obj-routename","maxclass" : "newobj","numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 400.0, 130.0, 100.0, 22.0 ], "text" : "route name" } },

			{ "box" : { "id" : "obj-opath1",   "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 560.0, 170.0, 120.0, 22.0 ], "text" : "live.path live_set" } },
			{ "box" : { "id" : "obj-observer1","maxclass" : "newobj","numinlets" : 2, "numoutlets" : 2, "patching_rect" : [ 560.0, 200.0, 230.0, 22.0 ], "text" : "live.observer @property current_song_time" } },
			{ "box" : { "id" : "obj-rtime",    "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 560.0, 230.0, 140.0, 22.0 ], "text" : "route current_song_time" } },

			{ "box" : { "id" : "obj-opath2",   "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 810.0, 170.0, 120.0, 22.0 ], "text" : "live.path live_set" } },
			{ "box" : { "id" : "obj-observer2","maxclass" : "newobj","numinlets" : 2, "numoutlets" : 2, "patching_rect" : [ 810.0, 200.0, 230.0, 22.0 ], "text" : "live.observer @property last_event_time" } },
			{ "box" : { "id" : "obj-rlen",     "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 810.0, 230.0, 140.0, 22.0 ], "text" : "route last_event_time" } },

			{ "box" : { "id" : "obj-cuepoints","maxclass" : "newobj","numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 560.0, 280.0, 220.0, 22.0 ], "text" : "M4L.api.GetCuePointNames" } },

			{ "box" : { "id" : "obj-js",  "maxclass" : "newobj","numinlets" : 9, "numoutlets" : 1, "patching_rect" : [ 30.0, 330.0, 200.0, 22.0 ], "text" : "js liverig_send.js" } },
			{ "box" : { "id" : "obj-udp", "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 365.0, 200.0, 22.0 ], "text" : "udpsend 127.0.0.1 9000" } },
			{ "box" : { "id" : "obj-print","maxclass":"newobj","numinlets":1,"numoutlets":0,"patching_rect":[ 260.0, 330.0, 150.0, 22.0 ],"text" : "print json_out" } },

			{ "box" : { "id" : "obj-c-sysex", "maxclass" : "comment", "numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 410.0, 500.0, 18.0 ],
				"text" : "─── SysEx from bridge → cue point navigation ───" } },

			{ "box" : { "id" : "obj-midiin",    "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 30.0, 435.0, 60.0, 22.0 ],  "text" : "midiin" } },
			{ "box" : { "id" : "obj-midiparse", "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 7, "patching_rect" : [ 30.0, 465.0, 80.0, 22.0 ],  "text" : "midiparse" } },
			{ "box" : { "id" : "obj-sxnav",     "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 30.0, 495.0, 200.0, 22.0 ], "text" : "zl slice 3" } },
			{ "box" : { "id" : "obj-sxcmd",     "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 4, "patching_rect" : [ 30.0, 525.0, 100.0, 22.0 ], "text" : "sel 48 49 50" } },

			{ "box" : { "id" : "obj-cue-next",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 30.0,  555.0, 130.0, 22.0 ], "text" : "call jump_to_next_cue" } },
			{ "box" : { "id" : "obj-cue-prev",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 170.0, 555.0, 130.0, 22.0 ], "text" : "call jump_to_prev_cue" } },

			{ "box" : { "id" : "obj-opath-cue", "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 30.0,  585.0, 120.0, 22.0 ], "text" : "live.path live_set" } },
			{ "box" : { "id" : "obj-lobj-cue",  "maxclass" : "newobj","numinlets" : 2, "numoutlets" : 2, "patching_rect" : [ 30.0,  615.0, 120.0, 22.0 ], "text" : "live.object" } },

			{ "box" : { "id" : "obj-footer", "maxclass" : "comment","numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 680.0, 1040.0, 60.0 ],
				"text" : "LOCATOR NAMING:  'Song: <name>' = song boundary on iPad Setlist page.  Any other name = section within current song.\nSysEx: F0 7D 31 00 F7 = next cue  |  F0 7D 32 00 F7 = previous cue.\n(We're using native Live API jump_to_next_cue / jump_to_prev_cue via live.object.)" } }
		],
		"lines" : [
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-metro",     0 ] } },
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-pathmsg",   0 ] } },
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-opath1",    0 ] } },
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-opath2",    0 ] } },
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-opath-cue", 0 ] } },
			{ "patchline" : { "source" : [ "obj-loadbang",   0 ], "destination" : [ "obj-metro",     0 ] } },
			{ "patchline" : { "source" : [ "obj-metro",      0 ], "destination" : [ "obj-transport", 0 ] } },
			{ "patchline" : { "source" : [ "obj-metro",      0 ], "destination" : [ "obj-getname",   0 ] } },
			{ "patchline" : { "source" : [ "obj-metro",      0 ], "destination" : [ "obj-cuepoints", 0 ] } },

			{ "patchline" : { "source" : [ "obj-transport",  0 ], "destination" : [ "obj-bar-int",   0 ] } },
			{ "patchline" : { "source" : [ "obj-transport",  1 ], "destination" : [ "obj-beat-int",  0 ] } },
			{ "patchline" : { "source" : [ "obj-transport",  4 ], "destination" : [ "obj-bpm-int",   0 ] } },
			{ "patchline" : { "source" : [ "obj-transport",  5 ], "destination" : [ "obj-tsig-zl",   0 ] } },
			{ "patchline" : { "source" : [ "obj-transport",  6 ], "destination" : [ "obj-sel-state", 0 ] } },

			{ "patchline" : { "source" : [ "obj-sel-state",  0 ], "destination" : [ "obj-msg-stop",  0 ] } },
			{ "patchline" : { "source" : [ "obj-sel-state",  1 ], "destination" : [ "obj-msg-play",  0 ] } },
			{ "patchline" : { "source" : [ "obj-msg-stop",   0 ], "destination" : [ "obj-js", 0 ] } },
			{ "patchline" : { "source" : [ "obj-msg-play",   0 ], "destination" : [ "obj-js", 0 ] } },

			{ "patchline" : { "source" : [ "obj-bar-int",   0 ], "destination" : [ "obj-js", 1 ] } },
			{ "patchline" : { "source" : [ "obj-bpm-int",   0 ], "destination" : [ "obj-js", 2 ] } },
			{ "patchline" : { "source" : [ "obj-tsig-zl",   0 ], "destination" : [ "obj-js", 3 ] } },
			{ "patchline" : { "source" : [ "obj-beat-int",  0 ], "destination" : [ "obj-js", 6 ] } },

			{ "patchline" : { "source" : [ "obj-pathmsg",   0 ], "destination" : [ "obj-lpath",     0 ] } },
			{ "patchline" : { "source" : [ "obj-lpath",     0 ], "destination" : [ "obj-lobj",      1 ] } },
			{ "patchline" : { "source" : [ "obj-getname",   0 ], "destination" : [ "obj-lobj",      0 ] } },
			{ "patchline" : { "source" : [ "obj-lobj",      0 ], "destination" : [ "obj-routename", 0 ] } },
			{ "patchline" : { "source" : [ "obj-routename", 0 ], "destination" : [ "obj-js",        4 ] } },

			{ "patchline" : { "source" : [ "obj-cuepoints", 0 ], "destination" : [ "obj-js",        5 ] } },

			{ "patchline" : { "source" : [ "obj-opath1",    0 ], "destination" : [ "obj-observer1", 1 ] } },
			{ "patchline" : { "source" : [ "obj-observer1", 0 ], "destination" : [ "obj-rtime",     0 ] } },
			{ "patchline" : { "source" : [ "obj-rtime",     0 ], "destination" : [ "obj-js",        7 ] } },

			{ "patchline" : { "source" : [ "obj-opath2",    0 ], "destination" : [ "obj-observer2", 1 ] } },
			{ "patchline" : { "source" : [ "obj-observer2", 0 ], "destination" : [ "obj-rlen",      0 ] } },
			{ "patchline" : { "source" : [ "obj-rlen",      0 ], "destination" : [ "obj-js",        8 ] } },

			{ "patchline" : { "source" : [ "obj-js",        0 ], "destination" : [ "obj-udp",       0 ] } },
			{ "patchline" : { "source" : [ "obj-js",        0 ], "destination" : [ "obj-print",     0 ] } },

			{ "patchline" : { "source" : [ "obj-midiin",    0 ], "destination" : [ "obj-midiparse", 0 ] } },
			{ "patchline" : { "source" : [ "obj-midiparse", 0 ], "destination" : [ "obj-sxnav",     0 ] } },
			{ "patchline" : { "source" : [ "obj-sxnav",     0 ], "destination" : [ "obj-sxcmd",     0 ] } },
			{ "patchline" : { "source" : [ "obj-sxcmd",     1 ], "destination" : [ "obj-cue-next",  0 ] } },
			{ "patchline" : { "source" : [ "obj-sxcmd",     2 ], "destination" : [ "obj-cue-prev",  0 ] } },
			{ "patchline" : { "source" : [ "obj-cue-next",  0 ], "destination" : [ "obj-lobj-cue",  0 ] } },
			{ "patchline" : { "source" : [ "obj-cue-prev",  0 ], "destination" : [ "obj-lobj-cue",  0 ] } },
			{ "patchline" : { "source" : [ "obj-opath-cue", 0 ], "destination" : [ "obj-lobj-cue",  1 ] } }
		]
	}
}
