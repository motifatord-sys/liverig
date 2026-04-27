{
	"patcher" : 	{
		"fileversion" : 1,
		"appversion" : 		{
			"major" : 9,
			"minor" : 0,
			"revision" : 10,
			"architecture" : "x64",
			"modernui" : 1
		}
,
		"classnamespace" : "box",
		"rect" : [ 4645.0, 203.0, 1100.0, 800.0 ],
		"gridsize" : [ 15.0, 15.0 ],
		"boxes" : [ 			{
				"box" : 				{
					"id" : "obj-title",
					"maxclass" : "comment",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 668.0, 11.0, 1040.0, 20.0 ],
					"text" : "LiveRig Bridge v13 — fixed SysEx routing via midiparse outlet 6"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-thisdevice",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 3,
					"outlettype" : [ "bang", "int", "int" ],
					"patching_rect" : [ 668.0, 41.0, 120.0, 22.0 ],
					"text" : "live.thisdevice"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-loadbang",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "bang" ],
					"patching_rect" : [ 808.0, 41.0, 80.0, 22.0 ],
					"text" : "loadbang"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-metro",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "bang" ],
					"patching_rect" : [ 668.0, 76.0, 80.0, 22.0 ],
					"text" : "metro 100"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-transport",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 9,
					"outlettype" : [ "int", "int", "float", "float", "float", "", "int", "float", "" ],
					"patching_rect" : [ 668.0, 111.0, 80.0, 22.0 ],
					"text" : "transport"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-bar-int",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "int" ],
					"patching_rect" : [ 668.0, 146.0, 40.0, 22.0 ],
					"text" : "int"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-beat-int",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "int" ],
					"patching_rect" : [ 718.0, 146.0, 40.0, 22.0 ],
					"text" : "int"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-bpm-int",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "int" ],
					"patching_rect" : [ 768.0, 146.0, 40.0, 22.0 ],
					"text" : "int"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-tsig-zl",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 818.0, 146.0, 60.0, 22.0 ],
					"text" : "zl nth 1"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-sel-state",
					"maxclass" : "newobj",
					"numinlets" : 3,
					"numoutlets" : 3,
					"outlettype" : [ "bang", "bang", "" ],
					"patching_rect" : [ 888.0, 146.0, 60.0, 22.0 ],
					"text" : "sel 0 1"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-msg-stop",
					"maxclass" : "message",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 888.0, 176.0, 70.0, 22.0 ],
					"text" : "stopped"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-msg-play",
					"maxclass" : "message",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 968.0, 176.0, 60.0, 22.0 ],
					"text" : "playing"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-c-song",
					"maxclass" : "comment",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 1038.0, 41.0, 650.0, 20.0 ],
					"text" : "live.path + live.object: song name. live.observer chains: current_song_time, last_event_time"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-lpath",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 3,
					"outlettype" : [ "", "", "" ],
					"patching_rect" : [ 1038.0, 71.0, 120.0, 22.0 ],
					"text" : "live.path"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-lobj",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 1038.0, 101.0, 120.0, 22.0 ],
					"saved_object_attributes" : 					{
						"_persistence" : 0
					}
,
					"text" : "live.object"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-pathmsg",
					"maxclass" : "message",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 1038.0, 41.0, 130.0, 22.0 ],
					"text" : "path live_set"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-getname",
					"maxclass" : "message",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 1173.0, 101.0, 80.0, 22.0 ],
					"text" : "get name"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-routename",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 1038.0, 131.0, 100.0, 22.0 ],
					"text" : "route name"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-opath1",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 3,
					"outlettype" : [ "", "", "" ],
					"patching_rect" : [ 1198.0, 171.0, 120.0, 22.0 ],
					"text" : "live.path live_set"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-observer1",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 1198.0, 201.0, 239.0, 22.0 ],
					"saved_object_attributes" : 					{
						"_persistence" : 0
					}
,
					"text" : "live.observer @property current_song_time"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-rtime",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 1198.0, 231.0, 140.0, 22.0 ],
					"text" : "route current_song_time"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-opath2",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 3,
					"outlettype" : [ "", "", "" ],
					"patching_rect" : [ 1448.0, 171.0, 120.0, 22.0 ],
					"text" : "live.path live_set"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-observer2",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 1448.0, 201.0, 230.0, 22.0 ],
					"saved_object_attributes" : 					{
						"_persistence" : 0
					}
,
					"text" : "live.observer @property last_event_time"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-rlen",
					"maxclass" : "newobj",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "", "" ],
					"patching_rect" : [ 1448.0, 231.0, 140.0, 22.0 ],
					"text" : "route last_event_time"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-js",
					"maxclass" : "newobj",
					"numinlets" : 9,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 668.0, 331.0, 200.0, 22.0 ],
					"saved_object_attributes" : 					{
						"filename" : "liverig_send.js",
						"parameter_enable" : 0
					}
,
					"text" : "js liverig_send.js"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-udp",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 668.0, 366.0, 200.0, 22.0 ],
					"text" : "udpsend 127.0.0.1 9000"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-print",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 898.0, 331.0, 150.0, 22.0 ],
					"text" : "print json_out"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-c-sysex",
					"maxclass" : "comment",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 668.0, 411.0, 700.0, 20.0 ],
					"text" : "─── SysEx F0 7D NN VV F7 → midiparse outlet 6 → liverig_dispatch.js → Live API call ───"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-midiin",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "int" ],
					"patching_rect" : [ 668.0, 436.0, 80.0, 22.0 ],
					"text" : "sysexin"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-print-sysex",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 898.0, 496.0, 130.0, 22.0 ],
					"text" : "print sysex_in"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-jsdispatch",
					"maxclass" : "newobj",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 668.0, 526.0, 220.0, 22.0 ],
					"saved_object_attributes" : 					{
						"filename" : "liverig_dispatch.js",
						"parameter_enable" : 0
					}
,
					"text" : "js liverig_dispatch.js"
				}

			}
, 			{
				"box" : 				{
					"id" : "obj-footer",
					"linecount" : 3,
					"maxclass" : "comment",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 668.0, 701.0, 847.0, 47.0 ],
					"text" : "LOCATOR NAMING:  'Song: <n>' = song boundary on iPad Setlist page.  Any other name = section within current song.\nNATIVE TRANSPORT (no Cmd+M mapping needed):  Play/Stop/Rec/Overdub/Metro/Loop/Punch/Tap/Undo/Redo all routed via Live API in liverig_dispatch.js.\nSysEx codes 0x40-0x49 = transport, 0x30-0x32 = markers."
				}

			}
 ],
		"lines" : [ 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 1 ],
					"source" : [ "obj-bar-int", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 6 ],
					"source" : [ "obj-beat-int", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 2 ],
					"source" : [ "obj-bpm-int", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-lobj", 0 ],
					"source" : [ "obj-getname", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-print", 0 ],
					"order" : 0,
					"source" : [ "obj-js", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-udp", 0 ],
					"order" : 1,
					"source" : [ "obj-js", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-metro", 0 ],
					"source" : [ "obj-loadbang", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-routename", 0 ],
					"source" : [ "obj-lobj", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-lobj", 1 ],
					"source" : [ "obj-lpath", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-getname", 0 ],
					"order" : 0,
					"source" : [ "obj-metro", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-transport", 0 ],
					"order" : 1,
					"source" : [ "obj-metro", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-jsdispatch", 0 ],
					"order" : 1,
					"source" : [ "obj-midiin", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-print-sysex", 0 ],
					"order" : 0,
					"source" : [ "obj-midiin", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 0 ],
					"source" : [ "obj-msg-play", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 0 ],
					"source" : [ "obj-msg-stop", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-rtime", 0 ],
					"source" : [ "obj-observer1", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-rlen", 0 ],
					"source" : [ "obj-observer2", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-observer1", 1 ],
					"source" : [ "obj-opath1", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-observer2", 1 ],
					"source" : [ "obj-opath2", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-lpath", 0 ],
					"source" : [ "obj-pathmsg", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 8 ],
					"source" : [ "obj-rlen", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 4 ],
					"source" : [ "obj-routename", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 7 ],
					"source" : [ "obj-rtime", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-msg-play", 0 ],
					"source" : [ "obj-sel-state", 1 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-msg-stop", 0 ],
					"source" : [ "obj-sel-state", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-metro", 0 ],
					"order" : 3,
					"source" : [ "obj-thisdevice", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-opath1", 0 ],
					"order" : 1,
					"source" : [ "obj-thisdevice", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-opath2", 0 ],
					"order" : 0,
					"source" : [ "obj-thisdevice", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-pathmsg", 0 ],
					"order" : 2,
					"source" : [ "obj-thisdevice", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-bar-int", 0 ],
					"source" : [ "obj-transport", 0 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-beat-int", 0 ],
					"source" : [ "obj-transport", 1 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-bpm-int", 0 ],
					"source" : [ "obj-transport", 4 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-sel-state", 0 ],
					"source" : [ "obj-transport", 6 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-tsig-zl", 0 ],
					"source" : [ "obj-transport", 5 ]
				}

			}
, 			{
				"patchline" : 				{
					"destination" : [ "obj-js", 3 ],
					"source" : [ "obj-tsig-zl", 0 ]
				}

			}
 ],
		"dependency_cache" : [ 			{
				"name" : "liverig_dispatch.js",
				"bootpath" : "~/Desktop/liverig",
				"patcherrelativepath" : ".",
				"type" : "TEXT",
				"implicit" : 1
			}
, 			{
				"name" : "liverig_send.js",
				"bootpath" : "~/Desktop/liverig",
				"patcherrelativepath" : ".",
				"type" : "TEXT",
				"implicit" : 1
			}
 ],
		"autosave" : 0,
		"oscreceiveudpport" : 0
	}

}
