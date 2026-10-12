"""CPU-only tests for the DAgger aggregation dataset pipeline (no GPU, no Docker)."""
from pathlib import Path
import json
import sys
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from yopo_dagger import build_dataset as bd
from yopo_repro.forest import generate
from yopo_repro.io import sha256_file,write_json_atomic

SCOPE = 'dagger_aggregation_rollout_not_benchmark'


def fake_sdf(folder,occupancy):
    return np.zeros(occupancy.shape,dtype=np.float32)


def make_base(root,specs):
    index = {'version':1,'status':'complete','scale':'full','format':'raw_float_depth_and_body_pose',
             'provenance':'synthetic test base','shards':[]}
    for sid,split,seed,samples in specs:
        folder = root/'shards'/('%03d'%sid);folder.mkdir(parents=True,exist_ok=True)
        write_json_atomic(folder/'scene.json',generate(seed))
        np.save(folder/'sdf.npy',np.zeros((4,4,4),np.float32))
        manifest = {'status':'complete','config':{'samples':samples},'completed_samples':samples,
                    'frame_sha256':[],'qa':[{'index':0,'checks':1,'p99_m':0.,'max_m':0.}],
                    'scene_sha256':sha256_file(folder/'scene.json'),'poses_sha256':'0'*64,
                    'depth_sha256':'0'*64,'provenance':'synthetic','source':'synthetic'}
        write_json_atomic(folder/'manifest.json',manifest)
        write_json_atomic(folder/'map.json',{'backend':'original_main_bucket','origin':[0.,0.,0.],
            'upper':[1.,1.,1.],'resolution':.2,'shape':[4,4,4],'sdf_sha256':sha256_file(folder/'sdf.npy'),
            'pointcloud_sha256':'0'*32})
        index['shards'].append({'id':sid,'split':split,'map_seed':seed,'pose_seed':None,'samples':samples,
            'density':1/30,'path':'shards/'+folder.name,
            'manifest_sha256':sha256_file(folder/'manifest.json'),'map_sha256':sha256_file(folder/'map.json')})
    write_json_atomic(root/'dataset.json',index)
    return index


def make_flight(folder,map_seed,count=4,scope=SCOPE,status='success',positions=None,quaternions=None,
                depth_transform=None,expect_qa_pass=True):
    folder.mkdir(parents=True,exist_ok=True)
    scene = generate(map_seed)
    if positions is None:
        positions = np.stack([np.array([-8.,0.,2.5])+i*np.array([.5,0.,0.]) for i in range(count)])
    if quaternions is None:quaternions = np.tile(np.array([1.,0.,0.,0.]),(count,1))
    depths = np.full((count,90,160),20.,np.float32)
    pixels = bd.pixel_probe()
    for i in range(count):
        expected = bd.render_reference_frame(scene,positions[i],quaternions[i],pixels)
        depths[i][pixels[:,1],pixels[:,0]] = np.clip(expected,0.,20.)
    if depth_transform is not None:depths = depth_transform(depths)
    frames = np.zeros((count,12))
    frames[:,0] = np.arange(count)*.1
    frames[:,1:4] = positions;frames[:,4:8] = quaternions;frames[:,11] = 1.
    np.savez_compressed(folder/'flight.npz',depths=depths,frames=frames)
    write_json_atomic(folder/'scene.json',scene)
    write_json_atomic(folder/'metrics.json',{'status':status,'scope':scope,'camera':bd.CAMERA_CONFIG,
        'checkpoint_sha256':'a'*64,'config':{'map_seed':map_seed}})
    return folder


def test_aggregation_index_and_base_untouched(tmp_path):
    base = tmp_path/'datasets'/'base';base.mkdir(parents=True)
    base_index = make_base(base,[(0,'train',100,1000),(1,'valid',1000,100),(2,'test',2000,100)])
    before = {shard['path']:sha256_file(base/shard['path']/'manifest.json') for shard in base_index['shards']}
    flights = tmp_path/'artifacts'/'flights';flights.mkdir(parents=True)
    make_flight(flights/'run_a',7000,count=4)
    output = tmp_path/'datasets'/'aggregation'
    summary = bd.aggregate(base,output,flights,{7000},qa_count=2,sdf_builder=fake_sdf)
    index = json.loads((output/'dataset.json').read_text(encoding='utf-8'))
    assert index['status']=='complete' and index['scale']=='dagger_aggregation'
    assert [shard['split'] for shard in index['shards']]==['train','valid','test','train']
    new = index['shards'][-1]
    assert new['id']==3 and new['map_seed']==7000 and new['samples']==4
    folder = output/new['path']
    depth = np.load(folder/'depth_m.npy');poses = dict(np.load(folder/'poses.npz'))
    assert depth.shape==(4,90,160) and depth.dtype==np.float32 and float(depth.max())<=20.
    assert poses['positions'].shape==(4,3) and poses['camera_positions'].shape==(4,3)
    assert np.max(np.abs(np.linalg.norm(poses['quaternions'],axis=1)-1))<1e-10
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['frame_sha256'])==4 and manifest['qa']
    assert sha256_file(folder/'depth_m.npy')==manifest['depth_sha256']
    assert manifest['flights'][0]['run']=='run_a' and manifest['flights'][0]['frames']==4
    catalog = json.loads((folder/'map.json').read_text(encoding='utf-8'))
    assert catalog['backend']=='original_main_bucket' and sha256_file(folder/'sdf.npy')==catalog['sdf_sha256']
    for shard in index['shards']:
        if shard['split'] in ('valid','test'):
            resolved = (output/shard['path']).resolve()
            assert resolved==(base/shard['base_path']).resolve()
    after = {shard['path']:sha256_file(base/shard['path']/'manifest.json') for shard in base_index['shards']}
    assert before==after
    assert summary['base_shards_verified']['0']['matches_index'] is True
    assert json.loads((output/'aggregation_manifest.json').read_text(encoding='utf-8'))['dataset_sha256']==sha256_file(output/'dataset.json')


def test_multiple_flights_on_one_map_concatenate(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    flights = tmp_path/'flights';flights.mkdir()
    make_flight(flights/'run_a',7000,count=3)
    make_flight(flights/'run_b',7000,count=5)
    output = tmp_path/'aggregation'
    bd.aggregate(base,output,flights,{7000},qa_count=1,sdf_builder=fake_sdf)
    index = json.loads((output/'dataset.json').read_text(encoding='utf-8'))
    assert len(index['shards'])==3
    new = index['shards'][-1]
    assert new['samples']==8
    manifest = json.loads((output/new['path']/'manifest.json').read_text(encoding='utf-8'))
    assert [f['run'] for f in manifest['flights']]==['run_a','run_b']


def test_rejects_forbidden_seed_and_undeclared_flight(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    flights = tmp_path/'flights';flights.mkdir();make_flight(flights/'run_a',7000,count=2)
    with pytest.raises(ValueError,match='validation/test/benchmark'):
        bd.aggregate(base,tmp_path/'out1',flights,{5000},qa_count=1,sdf_builder=fake_sdf)
    with pytest.raises(ValueError,match='outside the declared aggregation set'):
        bd.aggregate(base,tmp_path/'out2',flights,{7001},qa_count=1,sdf_builder=fake_sdf)
    with pytest.raises(ValueError,match='must not reuse base map seeds'):
        bd.aggregate(base,tmp_path/'out3',flights,{100},qa_count=1,sdf_builder=fake_sdf)


def test_rejects_wrong_scope_and_bad_frames(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    scope_dir = tmp_path/'scope';scope_dir.mkdir()
    make_flight(scope_dir/'benchmark_run',7000,scope='primary_frozen_benchmark',count=2)
    with pytest.raises(ValueError,match='aggregation scope tag'):
        bd.aggregate(base,tmp_path/'out1',scope_dir,{7000},qa_count=1,sdf_builder=fake_sdf)
    quat_dir = tmp_path/'quat';quat_dir.mkdir()
    make_flight(quat_dir/'nonunit',7001,count=2,quaternions=np.tile(np.array([2.,0.,0.,0.]),(2,1)))
    with pytest.raises(ValueError,match='not unit'):
        bd.aggregate(base,tmp_path/'out2',quat_dir,{7001},qa_count=1,sdf_builder=fake_sdf)
    nan_dir = tmp_path/'nan';nan_dir.mkdir()
    make_flight(nan_dir/'nonfinite',7002,count=2,
                depth_transform=lambda d:(d.__setitem__((0,0,0),np.nan) or d))
    with pytest.raises(ValueError,match='Non-finite depth'):
        bd.aggregate(base,tmp_path/'out3',nan_dir,{7002},qa_count=1,sdf_builder=fake_sdf)


def test_rejects_wrong_geometry_and_empty_flight(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    flights = tmp_path/'flights';flights.mkdir()
    pixels = bd.pixel_probe()
    def shift_probe_pixels(depths):
        out = depths.copy()
        out[:,pixels[:,1],pixels[:,0]] = np.clip(out[:,pixels[:,1],pixels[:,0]]-0.75,0.,20.)
        return out
    make_flight(flights/'shifted',7000,count=2,depth_transform=shift_probe_pixels)
    with pytest.raises(ValueError,match='geometry QA failed'):
        bd.aggregate(base,tmp_path/'out1',flights,{7000},qa_count=2,sdf_builder=fake_sdf)
    empty = tmp_path/'empty';empty.mkdir();make_flight(empty/'zero',7001,count=1)
    data = dict(np.load(empty/'zero'/'flight.npz'))
    np.savez_compressed(empty/'zero'/'flight.npz',depths=data['depths'][:0],frames=data['frames'][:0])
    with pytest.raises(ValueError,match='Empty flight record'):
        bd.aggregate(base,tmp_path/'out2',empty,{7001},qa_count=1,sdf_builder=fake_sdf)


def test_refuses_existing_output_and_output_inside_base(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    flights = tmp_path/'flights';flights.mkdir();make_flight(flights/'run_a',7000,count=2)
    output = tmp_path/'aggregation'
    bd.aggregate(base,output,flights,{7000},qa_count=1,sdf_builder=fake_sdf)
    with pytest.raises(ValueError,match='already exists'):
        bd.aggregate(base,output,flights,{7000},qa_count=1,sdf_builder=fake_sdf)
    with pytest.raises(ValueError,match='must not live inside the base dataset'):
        bd.aggregate(base,base/'nested',flights,{7000},qa_count=1,sdf_builder=fake_sdf)


def test_detects_changed_base_shard(tmp_path):
    base = tmp_path/'base';base.mkdir();make_base(base,[(0,'train',100,10),(1,'valid',1000,10)])
    flights = tmp_path/'flights';flights.mkdir();make_flight(flights/'run_a',7000,count=2)
    write_json_atomic(base/'shards'/'000'/'manifest.json',{'status':'complete','tampered':True})
    with pytest.raises(ValueError,match='no longer match their recorded hashes'):
        bd.aggregate(base,tmp_path/'out',flights,{7000},qa_count=1,sdf_builder=fake_sdf)
    assert not (tmp_path/'out').exists()


def test_aggregation_accepts_the_collection_driver_manifest(tmp_path):
    """The real collection writes flights.json, not a directory of flight folders."""
    flights = tmp_path/'flights';flights.mkdir()
    (flights/'run_a').mkdir();(flights/'run_b').mkdir()
    manifest = {'status':'complete','flights':[{'run':'run_a','path':str(flights/'run_a')},
                                               {'run':'run_b','path':str(flights/'run_b')}]}
    (flights/'flights.json').write_text(json.dumps(manifest),encoding='utf-8')
    resolved = bd.resolve_flight_folders(flights)
    assert [folder.name for folder in resolved]==['run_a','run_b']
    manifest['flights'][0]['path'] = 'artifacts/dagger_flights/run_c'
    (flights/'flights.json').write_text(json.dumps(manifest),encoding='utf-8')
    resolved = bd.resolve_flight_folders(flights)
    assert resolved[0].as_posix().endswith('/artifacts/dagger_flights/run_c')
    assert resolved[0].is_absolute()


def test_aggregation_still_accepts_a_plain_directory_of_flights(tmp_path):
    flights = tmp_path/'flights';flights.mkdir()
    (flights/'run_a').mkdir();(flights/'run_b').mkdir()
    assert [folder.name for folder in bd.resolve_flight_folders(flights)]==['run_a','run_b']
