#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, os, shutil, subprocess, tempfile
# KYTY_BETA_BASE: the release work directory (work/KytyPS5-Beta.AppDir, validation/) when it is not this tree.
base = Path(os.environ.get('KYTY_BETA_BASE') or Path(__file__).resolve().parent.parent)
repo = Path(__file__).resolve().parents[2]
bundle = base / 'work/KytyPS5-Beta.AppDir'
checks = []
def check(ok, name):
    if not ok: raise AssertionError(name)
    checks.append(name)
    print('PASS ' + name, flush=True)

manifest = json.loads((bundle / 'BUILD-MANIFEST.json').read_text())
for name, info in manifest['backends'].items():
    check(hashlib.file_digest((bundle / 'emulator/elf' / name).open('rb'),'sha256').hexdigest() == info['sha256'], 'Unchanged backend: ' + name)
for f in bundle.rglob('*'):
    if f.is_symlink():
        check(not os.path.isabs(os.readlink(f)) and f.exists(), 'Relocatable symlink: ' + str(f.relative_to(bundle))) if os.path.isabs(os.readlink(f)) or not f.exists() else None
check(all(not os.path.isabs(os.readlink(f)) and f.exists() for f in bundle.rglob('*') if f.is_symlink()), 'All runtime symlinks are relative and resolve')
for f in (bundle / 'patches').glob('*.json'):
    p = json.loads(f.read_text())
    check(all(not m.get('enabled') for m in p['mods']), 'Cheats initially disabled: ' + f.name)
for f in [bundle/'AppRun', bundle/'runtime-selector.sh', bundle/'selector-relocated.sh']:
    check('/home/david' not in f.read_text(), 'No developer path in ' + f.name)
    subprocess.run(['bash','-n',str(f)],check=True)
with tempfile.TemporaryDirectory(prefix='kyty-beta-package-') as temp:
    temp = Path(temp)
    env = os.environ.copy()
    env.update(KYTYPS5_BUNDLE_ROOT=str(bundle),KYTYPS5_DATA_ROOT=str(temp/'data'),KYTYPS5_CONFIG_ROOT=str(temp/'config'),KYTYPS5_PROFILE_ROOT=str(temp/'profiles'),PATH=str(bundle/'bin')+':'+env['PATH'])
    subprocess.run([str(bundle/'bin/python3'),str(bundle/'prepare-runtime.py'),'--init'],env=env,check=True)
    profile = temp/'profile.json'
    scanner = temp/'scanner'
    scanner.write_text('import sys\nprint(' + repr(str(profile)) + ')\n')
    env.update(KYTYPS5_UPSCALER_SCANNER=str(scanner),KYTY_EMULATOR_SELECTOR_DRY_RUN='1',KYTY_NATIVE_GPU_PM4_MODE='upstream')
    def route(extra, name, binary, contains=(), absent=(), args=None):
        e = env.copy(); e.update(extra)
        r = subprocess.run([str(bundle/'selector-relocated.sh'),*(args or ['--game',str(temp/'missing/eboot.bin')])],env=e,text=True,capture_output=True)
        check(r.returncode == 0, name + ' exits successfully: ' + r.stderr[-200:] if r.returncode else name + ' exits successfully')
        check('Executable: '+str(bundle/'emulator'/binary) in r.stdout, name + ' selects ' + binary)
        check(all(s in r.stdout for s in contains) and all(s not in r.stdout for s in absent), name + ' settings propagate')
    route({}, 'Native', 'kyty_emulator_native')
    route({'KYTY_NATIVE_GPU_PM4_MODE':'fast'}, 'Legacy Fast', 'kyty_emulator_fast')
    for adapter,binary in [('fsr3_description_v1','kyty_emulator_auto_upscaler'),('taa_paths_v1','kyty_emulator_launcher_taa_fg')]:
        profile.write_text(json.dumps({'capabilities':{'upscaler':{'state':'available'},'frame_generation':{'state':'available'}},'runtime':{'adapter':adapter}}))
        extra={'KYTY_NATIVE_UPSCALER_BUILD':'1','KYTY_UPSCALER':'game','KYTY_FRAMEGEN':'fsr3'}
        route(extra, adapter, binary, ['KYTY_FRAMEGEN=fsr3'])
    route(dict(extra,KYTY_BC250_TITLE_ID='PPSA01341',KYTY_DEMONS_SCREAM_ASSERT_RECOVERY='1'), 'Recovery after TAA selection', 'kyty_emulator_launcher_taa_fg', ['KYTY_DEMONS_SCREAM_ASSERT_RECOVERY=1'])
    route(dict(extra,KYTY_BC250_TITLE_ID='PPSA01341',KYTY_DEMONS_SCREAM_ASSERT_RECOVERY='0'), 'Recovery Off', 'kyty_emulator_launcher_taa_fg', absent=['KYTY_DEMONS_SCREAM_ASSERT_RECOVERY=1'])
    # Read-only validation against the developer's current real archive; never execute the game.
    original = Path('/home/david/astro-helix-framegen-20261110/manual/astro-manual.json')
    g = json.loads(original.read_text())['game']['location']
    archive = g['archive'] + '!/' + g['member'].rsplit('/',1)[0]
    route({'KYTY_NATIVE_UPSCALER_BUILD':'1','KYTY_UPSCALER':'game','KYTY_FRAMEGEN':'fsr3'}, 'Astro exact-SHA relocation', 'kyty_emulator_astro', ['KYTY_ASTRO_DECOUPLE=1'], args=['--game',archive])
    # Repeated package mounts must refresh only beta-owned asset/helper links.
    assetlink = temp/'data/runtime/assets'
    assetlink.unlink(); assetlink.symlink_to('/tmp/kyty-previous-mount/assets')
    subprocess.run([str(bundle/'bin/python3'),str(bundle/'prepare-runtime.py'),'--init'],env=env,check=True)
    check(assetlink.resolve() == (bundle/'assets').resolve(),'Asset links refresh after AppImage remount/update')
check(not (bundle/'upscalers/dlls').exists(), 'No generated Helix network/shader DLLs bundled')

# ---- The real scanner on the packaged Python (Beta 4 shipped a scanner that needed numpy, which the package lacks;
# the routing checks above use a stand-in scanner and could not notice). ------------------------------------------
py = str(bundle/'bin/python3')
scan_dir = bundle/'tools/upscaler-scan'
for f in sorted((repo/'tools/upscaler-scan').rglob('*')):
    rel = f.relative_to(repo/'tools/upscaler-scan')
    if f.is_file() and rel.parts[0] != 'tests' and '__pycache__' not in rel.parts and f.name != '.gitignore':
        check((scan_dir/rel).is_file() and (scan_dir/rel).read_bytes() == f.read_bytes(), 'Packaged scanner matches the source: ' + rel.as_posix())
r = subprocess.run([py, '-I', '-c', 'import numpy'], capture_output=True, text=True)
check(r.returncode != 0, 'Packaged Python has no numpy (so the tests below cover the path users run)')
r = subprocess.run([py, '-I', str(repo/'tools/upscaler-scan/tests/test_no_numpy.py')], capture_output=True, text=True)
check(r.returncode == 0 and 'OK' in r.stderr, 'Scanner byte-pattern indexes work without numpy: ' + r.stderr.strip().splitlines()[-1])
r = subprocess.run([py, '-I', '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import kyty_upscaler_scan.__main__, kyty_upscaler_scan.scan, '
                    'kyty_upscaler_scan.ffx, kyty_upscaler_scan.psml, kyty_upscaler_scan.gamefs, kyty_upscaler_scan.x86; '
                    'from kyty_upscaler_scan import x86; import os; sys.exit(0 if os.path.exists(x86.OBJDUMP) else 3)', str(scan_dir)],
                   capture_output=True, text=True, env=dict(os.environ, PATH=str(bundle/'bin') + ':' + os.environ['PATH']))
check(r.returncode == 0, 'Scanner modules import on the packaged Python and find the packaged objdump' + ('' if r.returncode == 0 else ': ' + r.stderr[-300:]))
with tempfile.TemporaryDirectory(prefix='kyty-beta-scan-') as temp:
    temp = Path(temp)
    env = os.environ.copy()
    env.update(KYTYPS5_BUNDLE_ROOT=str(bundle), KYTYPS5_DATA_ROOT=str(temp/'data'), KYTYPS5_CONFIG_ROOT=str(temp/'config'),
               KYTYPS5_PROFILE_ROOT=str(temp/'profiles'), KYTYPS5_UPSCALER_PROFILE_DIR=str(temp/'upscaler-profiles'),
               XDG_CACHE_HOME=str(temp/'cache'), PATH=str(bundle/'bin') + ':' + env['PATH'])
    for name in ('KYTY_UPSCALER', 'KYTY_FRAMEGEN', 'KYTY_UPSCALE_PRESET', 'KYTY_BC250_TITLE_ID'): env.pop(name, None)
    subprocess.run([py, str(bundle/'prepare-runtime.py'), '--init'], env=env, check=True)
    # An executable the scanner cannot analyse: a profile that says so, never a crash, and cached.
    odd = temp/'odd-game'; (odd/'sce_sys').mkdir(parents=True); (odd/'eboot.bin').write_bytes(b'not a SELF')
    r = subprocess.run([py, '-I', str(scan_dir/'kyty-upscaler-scan'), 'ensure', str(odd)], env=env, capture_output=True, text=True)
    made = Path(r.stdout.strip()) if r.stdout.strip() else None
    check(r.returncode == 0 and made is not None and made.is_file(), 'Unanalysable executable still gets a profile' + ('' if r.returncode == 0 else ': ' + r.stderr[-300:]))
    odd_profile = json.loads(made.read_text())
    check(odd_profile.get('runtime') is None and odd_profile['capabilities']['upscaler']['state'] != 'available', 'Unanalysable executable is marked unsupported')
    r = subprocess.run([py, '-I', str(scan_dir/'kyty-upscaler-scan'), 'status', str(odd)], env=env, capture_output=True, text=True)
    check(json.loads(r.stdout.strip().splitlines()[-1])['state'] not in ('available', 'error'), 'Launcher status line for an unanalysable executable is valid JSON')
    r = subprocess.run([py, '-I', str(scan_dir/'kyty-render-preset'), '--profile', str(made), '--preset', 'quality'], env=env, capture_output=True, text=True)
    check(r.returncode == 0 and not r.stdout.strip(), 'Render-preset tool accepts a profile without a runtime block')
    # The real scanner through the real selector: a failed or unsupported scan starts the native backend and says why.
    senv = dict(env, KYTY_EMULATOR_SELECTOR_DRY_RUN='1', KYTY_NATIVE_GPU_PM4_MODE='upstream', KYTY_NATIVE_UPSCALER_BUILD='1',
                KYTY_UPSCALER='auto', KYTY_UPSCALE_PRESET='quality', KYTY_FRAMEGEN='auto',
                KYTYPS5_UPSCALER_SCANNER=str(scan_dir/'kyty-upscaler-scan'))
    r = subprocess.run([str(bundle/'selector-relocated.sh'), '--game', str(odd)], env=senv, capture_output=True, text=True)
    check(r.returncode == 0 and 'Executable: ' + str(bundle/'emulator/kyty_emulator_native') in r.stdout, 'Unsupported game starts on the native backend')
    r = subprocess.run([str(bundle/'selector-relocated.sh'), '--game', str(temp/'missing')], env=senv, capture_output=True, text=True)
    check(r.returncode == 0 and 'upscaler scan of this game failed' in r.stderr, 'A failed scan is reported in the game log, not hidden')
    # A render preset the profile cannot provide falls back to the game's own upscaler instead of refusing the launch.
    fake = temp/'fake-profile.json'
    fake.write_text(json.dumps({'game': {'title_id': 'TEST00000', 'version': '01.000.000', 'sha256': '0' * 64},
        'capabilities': {'upscaler': {'state': 'available'}, 'frame_generation': {'state': 'available'}},
        'runtime': {'adapter': 'taa_paths_v1', 'taa': {'startup_render_presets': {'kind': 'mode_render_pair_v1', 'presets': {}}}}}))
    stand_in = temp/'stand-in-scanner'; stand_in.write_text('print(' + repr(str(fake)) + ')\n')
    shutil.copy2(scan_dir/'kyty-render-preset', temp/'kyty-render-preset')
    r = subprocess.run([str(bundle/'selector-relocated.sh'), '--game', str(odd)], env=dict(senv, KYTYPS5_UPSCALER_SCANNER=str(stand_in), KYTY_UPSCALER='hlx_fsr4'), capture_output=True, text=True)
    check(r.returncode == 0 and 'KYTY_UPSCALER=game' in r.stdout and "using the game's own upscaler" in r.stderr, 'Unavailable render preset falls back instead of refusing the launch')
    # Real games on this development PC, when present (read-only; never executed).
    for label, path, want in [
            ('Ghost of Yotei (FidelityFX FSR 3 route)', '/home/david/Downloads/Ghost of Yōtei Complete Edition/Ghost of Yōtei Complete Edition.zar', ('available', 'kyty_emulator_auto_upscaler')),
            ("Demon's Souls (TAA route)", '/home/david/Downloads/Demons Souls (v01.007) (Deluxe Edition) – BP 4.xx – PPSA01341 – FPKG/Demons Souls (v01.007) (Deluxe Edition) – BP 4.xx – PPSA01341 – FPKG.zar', ('available', 'kyty_emulator_launcher_taa_fg'))]:
        if not Path(path).is_file():
            print('SKIP real scan (game not on this PC): ' + label, flush=True); continue
        r = subprocess.run([str(bundle/'selector-relocated.sh'), '--game', path], env=dict(senv, KYTY_UPSCALER='hlx_fsr4'), capture_output=True, text=True)
        check(r.returncode == 0 and f'(upscaler {want[0]},' in r.stdout and 'Executable: ' + str(bundle/'emulator'/want[1]) in r.stdout and 'scan of this game failed' not in r.stderr,
              'Real scan on the packaged Python selects ' + want[1] + ': ' + label)
(base/'validation').mkdir(exist_ok=True)
(base/'validation/package-checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'game_executed':False},indent=2)+'\n')
print(str(len(checks)) + ' package checks passed')
