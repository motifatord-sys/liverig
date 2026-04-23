{
	"patcher" : {
		"fileversion" : 1,
		"appversion" : { "major" : 8, "minor" : 6, "revision" : 0, "architecture" : "x64", "modernui" : 1 },
		"classnamespace" : "dsp.midi",
		"rect" : [ 50.0, 50.0, 1000.0, 700.0 ],
		"boxes" : [
			{ "box" : { "id" : "obj-title", "maxclass" : "comment", "numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 10.0, 940.0, 20.0 ],
				"text" : "LiveRig Bridge v10 — uses transport object (proven working). JS writes to /tmp/liverig_state.json for Python bridge file watcher." } },
			{ "box" : { "id" : "obj-outlets", "maxclass" : "comment", "numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 30.0, 940.0, 20.0 ],
				"text" : "transport outlets: 1=bars 2=beats 3=units 4=PPQ 5=tempo 6=timesig(list) 7=state(0/1) 8=rawticks 9=clocksrc" } },

			{ "box" : { "id" : "obj-thisdevice", "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 30.0, 60.0, 120.0, 22.0 ], "text" : "live.thisdevice" } },
			{ "box" : { "id" : "obj-loadbang",   "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 170.0, 60.0, 80.0, 22.0 ],  "text" : "loadbang" } },
			{ "box" : { "id" : "obj-metro",       "maxclass" : "newobj", "numinlets" : 2, "numoutlets" : 1, "outlettype" : [ "bang" ], "patching_rect" : [ 30.0, 95.0, 80.0, 22.0 ],   "text" : "metro 100" } },

			{ "box" : { "id" : "obj-transport", "maxclass" : "newobj", "numinlets" : 0, "numoutlets" : 9,
				"outlettype" : [ "int", "int", "int", "int", "float", "list", "int", "int", "list" ],
				"patching_rect" : [ 30.0, 130.0, 80.0, 22.0 ], "text" : "transport" } },

			{ "box" : { "id" : "obj-bar-int",   "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 30.0,  165.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-beat-int",  "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 80.0,  165.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-bpm-int",   "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 130.0, 165.0, 40.0, 22.0 ], "text" : "int" } },
			{ "box" : { "id" : "obj-tsig-zl",  "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 180.0, 165.0, 60.0, 22.0 ], "text" : "zl nth 1" } },
			{ "box" : { "id" : "obj-sel-state", "maxclass" : "newobj", "numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 250.0, 165.0, 60.0, 22.0 ], "text" : "sel 0 1" } },
			{ "box" : { "id" : "obj-msg-stop",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 250.0, 195.0, 70.0, 22.0 ], "text" : "stopped" } },
			{ "box" : { "id" : "obj-msg-play",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 330.0, 195.0, 60.0, 22.0 ], "text" : "playing" } },

			{ "box" : { "id" : "obj-lpath",    "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 3, "patching_rect" : [ 550.0, 130.0, 120.0, 22.0 ], "text" : "live.path" } },
			{ "box" : { "id" : "obj-lobj",     "maxclass" : "newobj","numinlets" : 2, "numoutlets" : 2, "patching_rect" : [ 550.0, 165.0, 120.0, 22.0 ], "text" : "live.object" } },
			{ "box" : { "id" : "obj-pathmsg",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 680.0, 95.0,  130.0, 22.0 ], "text" : "path live_set" } },
			{ "box" : { "id" : "obj-getname",  "maxclass" : "message","numinlets" : 2, "numoutlets" : 1, "patching_rect" : [ 680.0, 165.0, 80.0,  22.0 ], "text" : "get name" } },
			{ "box" : { "id" : "obj-routename","maxclass" : "newobj","numinlets" : 1, "numoutlets" : 2, "patching_rect" : [ 550.0, 200.0, 100.0, 22.0 ], "text" : "route name" } },

			{ "box" : { "id" : "obj-cuepoints","maxclass" : "newobj","numinlets" : 1, "numoutlets" : 1, "patching_rect" : [ 780.0, 130.0, 200.0, 22.0 ], "text" : "M4L.api.GetCuePointNames" } },

			{ "box" : { "id" : "obj-js",  "maxclass" : "newobj","numinlets" : 7, "numoutlets" : 1, "patching_rect" : [ 30.0, 280.0, 200.0, 22.0 ], "text" : "js liverig_send.js" } },
			{ "box" : { "id" : "obj-udp", "maxclass" : "newobj","numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 315.0, 200.0, 22.0 ], "text" : "udpsend 127.0.0.1 9000" } },
			{ "box" : { "id" : "obj-print","maxclass":"newobj","numinlets":1,"numoutlets":0,"patching_rect":[ 260.0, 280.0, 150.0, 22.0 ],"text" : "print json_out" } },

			{ "box" : { "id" : "obj-footer", "maxclass" : "comment","numinlets" : 1, "numoutlets" : 0, "patching_rect" : [ 30.0, 380.0, 940.0, 40.0 ],
				"text" : "JS writes /tmp/liverig_state.json every 100ms. Python bridge polls the file and broadcasts via WebSocket to iPad." } }
		],
		"lines" : [
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-metro",     0 ] } },
			{ "patchline" : { "source" : [ "obj-thisdevice", 0 ], "destination" : [ "obj-pathmsg",   0 ] } },
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

			{ "patchline" : { "source" : [ "obj-js",        0 ], "destination" : [ "obj-udp",       0 ] } },
			{ "patchline" : { "source" : [ "obj-js",        0 ], "destination" : [ "obj-print",     0 ] } }
		]
	}
}
