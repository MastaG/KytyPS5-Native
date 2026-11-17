#!/usr/bin/env python3
"""Marvel's Wolverine (PPSA03671 01.001.005): a render preset's plan, as a game-patch JSON.

usage: wolverine-render-preset.py PRESET OUT_FILE [--framegen]
       PRESET: dlaa | ultra_quality | quality | balanced | performance | ultra_performance
       --framegen: frame generation is on (Fidelity then renders at most FRAMEGEN_FIDELITY_MAX, see below)

The game's dynamic resolution picks render sizes from a table in its executable (0x9b7e7d0: 11 steps of
{width, height, cost in three mode columns}, 3840x2160 down to 1664x936; a 0 cost leaves a step out of that column).
Init (0x3f83d1e) copies it; column 0 is a prefix, columns 1 and 2 are ranges; rows 0/2 size the render targets.
Measured 2026-11-17: columns 0 and 1 (Fidelity, menus) upscale to 3840x2160 and column 2 (Performance) to 2560x1440,
which the game stretches to its 4K output; the game keeps these targets whatever the window size.

Each mode gets one size, its target divided by the preset's ratio (FSR's: 1.3, 1.5, 1.7, 2.0, 3.0), width rounded
down to a multiple of 128 like the game's own steps (heights then multiples of 72: the game asserts on sizes it does
not expect, e.g. 3776x2124), rows 0-6 for columns 0/1, rows 7-10 for column 2. The size always stays below the mode's
target: at the target the game switches to a non-upscaling pass the profile does not cover, so "dlaa" (native AA)
renders at the game's largest size below it (3328x1872 for Fidelity, 2432x1368 for Performance)."""
import json, struct, sys

TABLE = 0x9b7e7d0
ROWS = [(3840, 2160, 4.25, 0, 0), (3584, 2016, 4.25, 0, 0), (3328, 1872, 4, 4, 0), (3072, 1728, 3.75, 3.75, 0),
        (2816, 1584, 3.75, 3.75, 0), (2560, 1440, 3.5, 3.5, 3.5), (2304, 1296, 3, 3, 3), (2048, 1152, 2.5, 2.5, 2.5),
        (1920, 1080, 0, 1.75, 1.75), (1792, 1008, 0, 1.75, 1.75), (1664, 936, 0, 1, 1)]
FIDELITY_ROWS = range(0, 7)  # columns 0 and 1
PERFORMANCE_ROWS = range(7, 11)  # column 2
RATIOS = {'dlaa': None, 'ultra_quality': 1.3, 'quality': 1.5, 'balanced': 1.7, 'performance': 2.0, 'ultra_performance': 3.0}


FIDELITY_TARGET, PERFORMANCE_TARGET = (3840, 2160), (2560, 1440)


# Fidelity runs at 30 fps with almost no time to spare. Measured 2026-11-17 in the new game's first area (5-minute runs,
# HLX FSR 4 to 4K): Quality (2560x1440) holds 30 with HLX alone but falls to 20 with frame generation, whatever frame
# generation's working size (4K, 1440p or 1080p alike) or the GPU job streaming; Balanced (2176x1224) holds 30 + 30. With
# frame generation on, Fidelity therefore renders at most this size (Performance, 60 fps by itself, is not affected).
FRAMEGEN_FIDELITY_MAX = (2176, 1224)


# The game sizes its render targets for at most its base-PS5 maximum step (3328x1872; 3840x2160 is the PS5 Pro's):
# a larger size fails an allocation check at start (an ud2 at eboot 0x382e8fd, seen with 3776x2124 and 3712x2088).
MAX_WIDTH = 3328


def size_for(target_w, target_h, ratio):
    w = int(target_w / ratio) // 128 * 128 if ratio else target_w // 128 * 128
    if w >= target_w:
        w -= 128
    w = max(min(w, MAX_WIDTH), 384)
    return w, w * target_h // target_w


def plan(preset, framegen=False):
    ratio = RATIOS[preset]
    fid = size_for(*FIDELITY_TARGET, ratio)
    if framegen and fid[0] > FRAMEGEN_FIDELITY_MAX[0]:
        fid = FRAMEGEN_FIDELITY_MAX
    perf = size_for(*PERFORMANCE_TARGET, ratio)
    row = lambda w, h, c: struct.pack('<IIfff', w, h, *c).hex()
    mem = []
    for i, (w, h, a, b, c) in enumerate(ROWS):
        if i in FIDELITY_ROWS:
            cost = a or b
            new = (fid[0], fid[1], (cost, cost, 0.0))
        else:
            new = (perf[0], perf[1], (0.0, 0.0, c or b))
        mem.append({'offset': f'{TABLE + i * 20:x}', 'off': row(w, h, (a, b, c)), 'on': row(new[0], new[1], new[2])})
    name = (f'{preset}{" (frame generation)" if framegen else ""}: Fidelity {fid[0]}x{fid[1]} -> 3840x2160, '
            f'Performance {perf[0]}x{perf[1]} -> 2560x1440')
    return {'id': 'PPSA03671', 'version': '01.001.005', 'process': 'eboot.bin',
            'mods': [{'name': name, 'enabled': True, 'memory': mem}]}, fid, perf


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--framegen']
    if len(args) != 2 or args[0] not in RATIOS:
        raise SystemExit(__doc__)
    sys.argv[1:3] = args
    p, fid, perf = plan(args[0], '--framegen' in sys.argv[1:])
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(p, f, indent=1)
    print(f'{fid[0]}x{fid[1]} {perf[0]}x{perf[1]}')
