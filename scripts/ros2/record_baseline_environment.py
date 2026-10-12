from pathlib import Path
import argparse
import json
import platform
import subprocess
import sys
from importlib import metadata
parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);args=parser.parse_args()
release=dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
versions={}
for package in ['tensorflow-cpu','keras','numpy','scipy','opencv-python-headless']:
    try:versions[package]=metadata.version(package)
    except metadata.PackageNotFoundError:pass
out=Path('/workspace/artifacts/environment')
(out/(args.name+'_environment.json')).write_text(json.dumps({'os_release':release,'python':sys.version,
    'python_executable':sys.executable,'platform':platform.platform(),'versions':versions},indent=2)+'\n')
(out/(args.name+'_pip_freeze.txt')).write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
print(args.name,release.get('VERSION_ID'),platform.python_version(),versions)
