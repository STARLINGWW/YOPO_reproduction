"""Snapshot source/configuration evidence before formal training; no model files."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT=Path('/workspace')
parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);args=parser.parse_args()
output=ROOT/'artifacts/provenance'/args.name;output.mkdir(parents=True,exist_ok=False)
files=[]
for directory in ['src','scripts','configs','docker','ros2_ws/src','external/audit_sources/main']:
    for path in (ROOT/directory).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pth','.pt'):
            files.append(path)
files += [ROOT/'compose.yaml',ROOT/'artifacts/environment/pip_freeze_training.txt']
manifest={}
with zipfile.ZipFile(output/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        relative=path.relative_to(ROOT).as_posix();archive.write(path,relative)
        manifest[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
(output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('SOURCES_ARCHIVED '+str(output))
