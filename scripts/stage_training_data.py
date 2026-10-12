"""Copy a validated immutable dataset into the project Docker volume for mmap IO."""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT=Path('/workspace');sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic

parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);args=parser.parse_args()
if Path(args.name).name!=args.name or args.name in ('.','..'):raise ValueError('Invalid dataset name')
source=ROOT/'datasets'/args.name;target=Path('/data')/args.name;temporary=Path('/data')/(args.name+'.staging')
index=json.loads((source/'dataset.json').read_text(encoding='utf-8'))
validation=json.loads((source/'validation.json').read_text(encoding='utf-8'))
expected_hash=sha256_file(source/'dataset.json')
assert index['status']=='complete' and validation['status']=='passed' and validation['dataset_sha256']==expected_hash
assert validation['counts']=={'train':100000,'valid':10000,'test':10000}
if target.exists():
    assert sha256_file(target/'dataset.json')==expected_hash,'Existing volume dataset differs'
    print('DATA_VOLUME_REUSE '+str(target))
else:
    shutil.copytree(source,temporary,dirs_exist_ok=True)
    assert sha256_file(temporary/'dataset.json')==expected_hash
    temporary.rename(target)
write_json_atomic(ROOT/'artifacts/environment/data_volume.json',{'source':str(source),'target':str(target),
                  'volume':'yopo-ros2-reproduction_yopo-data','dataset_sha256':expected_hash,'counts':validation['counts']})
print('DATA_STAGED '+str(target))
