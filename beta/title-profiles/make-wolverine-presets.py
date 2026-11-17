#!/usr/bin/env python3
"""Marvel's Wolverine (PPSA03671 01.001.005) render presets for the HLX route, written beside this script.

The game's dynamic resolution picks render sizes from a table in its executable (0x9b7e7d0: 11 steps of
{width, height, cost in the Fidelity, Performance and third modes}, 3840x2160 down to 1664x936; a 0 cost leaves the
step out of that mode; init at 0x3f83d1e copies it, and rows 0/2 size the render targets).
- ultra-quality / quality / balanced / performance / ultra-performance: every step gets one size, so whatever the
  game's scaler picks it renders at that size in every mode (and allocates its targets at it)."""
import json, struct
from pathlib import Path

TABLE = 0x9b7e7d0
ROWS = [(3840, 2160, 4.25, 0, 0), (3584, 2016, 4.25, 0, 0), (3328, 1872, 4, 4, 0), (3072, 1728, 3.75, 3.75, 0),
        (2816, 1584, 3.75, 3.75, 0), (2560, 1440, 3.5, 3.5, 3.5), (2304, 1296, 3, 3, 3), (2048, 1152, 2.5, 2.5, 2.5),
        (1920, 1080, 0, 1.75, 1.75), (1792, 1008, 0, 1.75, 1.75), (1664, 936, 0, 1, 1)]
FIXED = {'ultra-quality': (2816, 1584), 'quality': (2560, 1440), 'balanced': (2304, 1296), 'performance': (1920, 1080),
         'ultra-performance': (1664, 936)}
PREFIX = 'PPSA03671-01.001.005'


def row(w, h, c):
    return struct.pack('<IIfff', w, h, *c).hex()


def plan(name, writes):
    return {'id': 'PPSA03671', 'version': '01.001.005', 'process': 'eboot.bin',
            'mods': [{'name': name, 'enabled': True, 'memory': writes}]}


here = Path(__file__).resolve().parent
out = {}
for preset, (fw, fh) in FIXED.items():
    out[preset] = plan(f'Fixed {fw}x{fh} render resolution (every dynamic-resolution step, every graphics mode)',
                       [{'offset': f'{TABLE + i * 20:x}', 'off': row(w, h, (a, b, c)), 'on': row(fw, fh, (a, b, c))}
                        for i, (w, h, a, b, c) in enumerate(ROWS)])
for preset, p in out.items():
    (here / f'{PREFIX}-{preset}.json').write_text(json.dumps(p, indent=2) + '\n')
    print(preset, len(p['mods'][0]['memory']), 'writes')
