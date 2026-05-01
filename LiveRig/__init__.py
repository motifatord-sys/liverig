"""LiveRig Remote Script for Ableton Live 11/12.
Loaded by Live when 'LiveRig' is selected as a Control Surface in Preferences > MIDI.

Install: copy this folder to ~/Music/Ableton/User Library/Remote Scripts/LiveRig/
Then in Live: Preferences > Link/Tempo/MIDI > Control Surface, pick 'LiveRig'.
Set Input + Output both to 'LiveRig Bridge' (the virtual port).
"""
from __future__ import absolute_import, print_function, unicode_literals

from .LiveRig import LiveRig

def create_instance(c_instance):
    return LiveRig(c_instance)
