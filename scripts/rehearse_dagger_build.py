"""Host-side rehearsal of the DAgger aggregation build, including the real
reference-SDF container call.

The unit tests inject a fake SDF builder, so the one part of the DAgger chain
that had never actually run was `docker compose ... sdf_reference`. This script
builds a synthetic but structurally real flight (camera block, scope tag, ray
consistent probe pixels), runs the real builder on the host, and leaves the
resulting shard plus a manifest under artifacts/dagger_rehearsal/ as evidence.
It is a rehearsal, not on-policy data: the folder and manifest say so.
"""
from pathlib import Path
import json
import shutil
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from yopo_repro.io import write_json_atomic
from yopo_repro.forest import generate
from yopo_dagger import build_dataset as builder

REHEARSAL = ROOT/'artifacts/dagger_rehearsal'
FLIGHT_RUN = 'rehearsal_flight_7000'
MAP_SEED = 7000


def make_synthetic_flight():
    folder = REHEARSAL/'flights'/FLIGHT_RUN
    if folder.exists():shutil.rmtree(folder)
    folder.mkdir(parents=True)
    scene = generate(MAP_SEED)
    count = 6
    positions = np.stack([np.array([-8.,0.,2.5])+index*np.array([.4,0.,0.]) for index in range(count)])
    quaternions = np.tile(np.array([1.,0.,0.,0.]),(count,1))
    depths = np.full((count,90,160),20.,np.float32)
    pixels = builder.pixel_probe()
    for index in range(count):
        expected = builder.render_reference_frame(scene,positions[index],quaternions[index],pixels)
        depths[index][pixels[:,1],pixels[:,0]] = np.clip(expected,0.,20.)
    frames = np.zeros((count,12));frames[:,0] = np.arange(count)*.1
    frames[:,1:4] = positions;frames[:,4:8] = quaternions;frames[:,11] = 1.
    np.savez_compressed(folder/'flight.npz',depths=depths,frames=frames)
    write_json_atomic(folder/'scene.json',scene)
    write_json_atomic(folder/'metrics.json',{'status':'success','scope':'dagger_aggregation_rollout_not_benchmark',
        'camera':builder.CAMERA_CONFIG,'checkpoint_sha256':'0'*64,'config':{'map_seed':MAP_SEED},
        'note':'synthetic rehearsal flight; no Isaac process was launched'})
    return folder


def main():
    REHEARSAL.mkdir(parents=True,exist_ok=True)
    make_synthetic_flight()
    output = REHEARSAL/'dataset'
    if output.exists():shutil.rmtree(output)
    builder.main(['--base',str(ROOT/'datasets/isaac_full_v1'),'--flights',str(REHEARSAL/'flights'),
                  '--output',str(output),'--allow-map-seeds',str(MAP_SEED),'--qa-frames','3'])
    index = json.loads((output/'dataset.json').read_text(encoding='utf-8'))
    shard = index['shards'][-1]
    folder = output/shard['path']
    catalog = json.loads((folder/'map.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert catalog['backend']=='original_main_bucket'
    assert (folder/'sdf.npy').is_file() and (folder/'pointcloud.ply').is_file()
    assert manifest['qa'] and manifest['completed_samples']==6
    assert len(index['shards'])==29  # 28 base shards plus the rehearsal shard
    write_json_atomic(REHEARSAL/'rehearsal_result.json',{'status':'passed',
        'scope':'synthetic rehearsal of the DAgger build, including the real reference-SDF container call; not on-policy data',
        'shard_id':shard['id'],'samples':shard['samples'],'qa_frames':len(manifest['qa']),
        'map_json':str((folder/'map.json').relative_to(ROOT).as_posix()),
        'dataset_json':str((output/'dataset.json').relative_to(ROOT).as_posix()),
        'note':'delete artifacts/dagger_rehearsal before the real collection if you want a clean tree'})
    print('REHEARSAL_OK shard=%d samples=%d qa=%d'%(shard['id'],shard['samples'],len(manifest['qa'])))


if __name__=='__main__':main()
