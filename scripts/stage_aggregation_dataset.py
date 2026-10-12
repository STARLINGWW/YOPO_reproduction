"""Stage the DAgger aggregation dataset into the project data volume.

Unlike the formal dataset stager this accepts a train split that is larger than
the base 100k samples, checks the base dataset is already staged with the same
content hash, and verifies every referenced base shard still matches its
recorded hashes. Relative base paths make the aggregation index depend on the
two dataset directories staying siblings inside the volume.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path('/workspace')
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic

parser = argparse.ArgumentParser()
parser.add_argument('--name',required=True)
parser.add_argument('--base-name',default='isaac_full_v1')
args = parser.parse_args()
for value in (args.name,args.base_name):
    if Path(value).name!=value or value in ('.','..'):raise ValueError('Invalid dataset name')
source = ROOT/'datasets'/args.name;target = Path('/data')/args.name;temporary = Path('/data')/(args.name+'.staging')
base_volume = Path('/data')/args.base_name
index = json.loads((source/'dataset.json').read_text(encoding='utf-8'))
if index['status']!='complete' or index.get('scale')!='dagger_aggregation':
    raise ValueError('Aggregation dataset is not complete')
aggregation = json.loads((source/'aggregation_manifest.json').read_text(encoding='utf-8'))
if aggregation['status']!='complete':raise ValueError('Aggregation manifest is not complete')
if not (base_volume/'dataset.json').is_file():raise ValueError('Base dataset must be staged first')
if sha256_file(base_volume/'dataset.json')!=sha256_file(Path(aggregation['base_dataset'])/'dataset.json'):
    raise ValueError('Staged base dataset differs from the aggregation baseline')
for shard in index['shards']:
    folder = source/shard['path']
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    maps = json.loads((folder/'map.json').read_text(encoding='utf-8'))
    if sha256_file(folder/'manifest.json')!=shard['manifest_sha256']:raise ValueError('Manifest hash changed: '+shard['path'])
    if sha256_file(folder/'map.json')!=shard['map_sha256']:raise ValueError('Map hash changed: '+shard['path'])
    if sha256_file(folder/'sdf.npy')!=maps['sdf_sha256']:raise ValueError('SDF hash changed: '+shard['path'])
    if sha256_file(folder/'depth_m.npy')!=manifest['depth_sha256']:raise ValueError('Depth hash changed: '+shard['path'])
expected_hash = sha256_file(source/'dataset.json')
if target.exists():
    assert sha256_file(target/'dataset.json')==expected_hash,'Existing volume dataset differs'
    print('AGGREGATION_VOLUME_REUSE '+str(target))
else:
    shutil.copytree(source,temporary,dirs_exist_ok=True)
    assert sha256_file(temporary/'dataset.json')==expected_hash
    temporary.rename(target)
counts = {}
for shard in index['shards']:counts[shard['split']] = counts.get(shard['split'],0)+int(shard['samples'])
write_json_atomic(ROOT/'artifacts/environment/aggregation_volume.json',{'source':str(source),'target':str(target),
    'volume':'yopo-ros2-reproduction_yopo-data','dataset_sha256':expected_hash,'counts':counts,
    'base_dataset':str(base_volume),'base_layout_rule':index['base_dataset_path_rule']})
print('AGGREGATION_STAGED '+str(target))
