#!/usr/bin/env python3
"""ASTRO BOT 01.018.000 render presets beyond Ultra Quality, derived from the validated Ultra Quality pair.

The Ultra Quality render patch (made by make-ultra-plan.py from the executable) forces the game's resolution tier 3
(`mov eax,3` at c62a97) and rewrites tier 3's size from 3328x1872 to 2944x1656 in three integer tables, three float
tables and three `mov [rdi],w / mov [rsi],h` immediates, each matched against the original bytes. Every preset here
keeps those addresses and original bytes and only changes the size, so the emulator still refuses a mismatching
executable (runtimeLinker: "Render preset did not match the loaded executable").
usage: make-astro-presets.py TEMPLATE_DIR      (writes astro-<preset>.json and astro-<preset>-render.json there)"""
import copy, json, struct, sys
from pathlib import Path

# Exact 16:9 sizes with heights in multiples of 72 (so both sides stay multiples of 8), as Ultra Quality's 2944x1656.
PRESETS = {
    'quality': (2560, 1440, 'Quality'),
    'balanced': (2304, 1296, 'Balanced'),
    'performance': (1920, 1080, 'Performance'),
    'ultra_performance': (1280, 720, 'Ultra Performance'),
}
UQ = (2944, 1656)

d = Path(sys.argv[1])
render = json.loads((d / 'astro-ultra-quality-render.json').read_text())
profile = json.loads((d / 'astro-ultra-quality.json').read_text())
writes = render['mods'][0]['memory']
assert writes[0] == {'offset': 'c62a97', 'off': '8b83f0230000', 'on': 'b80300000090'}, 'tier selector changed'
def ints(w, h): return struct.pack('<5I', 1920, 2432, 2432, w, 3840), struct.pack('<5I', 1080, 1368, 1368, h, 2160)
def floats(w): return struct.pack('<5f', 1920, 2432, 2432, w, 3840)
def code(w, h): return b'\xc7\x07' + struct.pack('<I', w) + b'\xc7\x06' + struct.pack('<I', h)
old_iw, old_ih = ints(*UQ); old_f = floats(UQ[0]); old_c = code(*UQ)
kinds = {old_iw.hex(): 'iw', old_ih.hex(): 'ih', old_f.hex(): 'f', old_c.hex(): 'c'}
counts = {}
for wr in writes[1:]:
    kind = kinds[wr['on']]
    counts[kind] = counts.get(kind, 0) + 1
assert counts == {'iw': 3, 'ih': 3, 'f': 3, 'c': 3}, counts
for name, (w, h, label) in PRESETS.items():
    iw, ih = ints(w, h)
    new = {'iw': iw.hex(), 'ih': ih.hex(), 'f': floats(w).hex(), 'c': code(w, h).hex()}
    plan = copy.deepcopy(render)
    plan['mods'][0]['name'] = f'Manual {label} {w}x{h} render tier'
    for wr in plan['mods'][0]['memory'][1:]:
        wr['on'] = new[kinds[wr['on']]]
    file = 'astro-' + name.replace('_', '-')
    (d / (file + '-render.json')).write_text(json.dumps(plan, indent=2) + '\n')
    p = copy.deepcopy(profile)
    p['runtime']['taa']['startup_render_presets'] = {'manual_fixed': f'{name}_{h}', 'plan': file + '-render.json'}
    p['manual_scenario'] = f'FSR4 {w}x{h} to 3840x2160 {label}'
    (d / (file + '.json')).write_text(json.dumps(p, indent=2) + '\n')
    print(f'{file}: {w}x{h}')
