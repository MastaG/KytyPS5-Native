#!/usr/bin/env python3
from pathlib import Path
import os, stat, sys, tarfile, zipfile
base = Path(os.environ.get('KYTY_BETA_BASE') or Path(__file__).resolve().parent.parent)
kind = sys.argv[1]
root = base/'work/KytyPS5-Beta.AppDir'
version = (root/'VERSION').read_text().strip()
name = f'KytyPS5-BC250-{version}-x86_64'
dist = base/'dist'; dist.mkdir(exist_ok=True)
if kind == 'tar':
    def neutral(info):
        # The packager's account is not package content.
        info.uid = info.gid = 0; info.uname = info.gname = 'root'
        return info
    with tarfile.open(dist/(name+'.tar.gz'),'w:gz',compresslevel=6) as t: t.add(root,arcname=name,filter=neutral)
elif kind == 'zip':
    with zipfile.ZipFile(dist/(name+'.zip'),'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(root.rglob('*')):
            arc = name+'/'+p.relative_to(root).as_posix()
            if p.is_symlink():
                info=zipfile.ZipInfo(arc)
                info.create_system=3; info.external_attr=(stat.S_IFLNK|0o777)<<16
                z.writestr(info,os.readlink(p).encode())
            elif p.is_file() or p.is_dir():
                z.write(p, arc)  # Include empty runtime directories in the portable ZIP.
elif kind == 'source':
    def keep(info):
        if any(part in ('artifacts','bin','obj','__pycache__','.git','.packages') for part in Path(info.name).parts): return None
        if info.name.endswith(('.pyc','.o','.dll','.exe','.so')): return None
        return info
    source_name = f'KytyPS5-BC250-{version}-source'
    with tarfile.open(dist/(source_name+'.tar.gz'),'w:gz',compresslevel=6) as t:
        t.add(base/'work/source',arcname=source_name,filter=keep)
else: raise SystemExit('Choose tar, zip or source')
print('Created '+kind+' archive',flush=True)
