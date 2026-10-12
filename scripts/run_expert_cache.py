"""Resumable fixed-test expert outputs; solver settings frozen before test use."""
from pathlib import Path
import argparse,hashlib,json,signal,sys,time
import numpy as np
ROOT=Path('/workspace');sys.path.insert(0,str(ROOT/'src'))
from yopo_expert.core import ExpertMap,world_problem
from yopo_repro.policy import load_config
from yopo_repro.dataset import ForestDataset,stack_batch
from yopo_repro.io import sha256_file,write_json_atomic
from flightpolicy.yopo.primitive_utils import LatticeParam,LatticePrimitive


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',type=Path,default=Path('/data/isaac_full_v1'))
    parser.add_argument('--run',default='formal_test_v1');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    output=(ROOT/'artifacts/expert'/args.run).resolve()
    if not output.is_relative_to(ROOT/'artifacts/expert'):raise ValueError('Invalid output path')
    validation=json.loads((args.dataset/'validation.json').read_text());assert validation['status']=='passed' and validation['counts']['test']==10000
    profile,cfg=load_config();dataset=ForestDataset(args.dataset,'test',cfg,seed=0);assert len(dataset)==10000
    sources=[Path(__file__),ROOT/'src/yopo_expert/core.py',ROOT/'src/yopo_repro/dataset.py',
             ROOT/'configs/expert_variants.json',ROOT/profile['trajectory_yaml'],
             ROOT/'ros2_ws/install/yopo_expert_core/lib/libyopo_expert.so']
    config={'dataset_sha256':sha256_file(args.dataset/'dataset.json'),'state_seed':0,'split':'test','samples':len(dataset),
            'source_sha256':{p.relative_to(ROOT).as_posix():sha256_file(p) for p in sources},
            'variants':json.loads((ROOT/'configs/expert_variants.json').read_text()),
            'scope':'Expert-only offline test cache, explicitly reconstructed solver settings. Final network comparison pending; no test-based tuning.'}
    if args.resume:
        if json.loads((output/'config.json').read_text())!=config:raise ValueError('Resume configuration/source/data mismatch')
        first=json.loads((output/'progress.json').read_text())['completed_samples'];mode='r+'
    else:
        output.mkdir(parents=True,exist_ok=False);write_json_atomic(output/'config.json',config);first=0;mode='w+'
    shapes={'initial_cost':(len(dataset),15),'states':(len(dataset),22)}
    for variant in ['scaled_gd50','mma50_evaluations']:
        shapes[variant+'_cost']=(len(dataset),15);shapes[variant+'_ends_world']=(len(dataset),15,3,3);shapes[variant+'_diagnostics']=(len(dataset),15,5)
    arrays={name:np.lib.format.open_memmap(output/(name+'.npy'),mode=mode,dtype=np.float64,shape=shape) for name,shape in shapes.items()}
    lattice=LatticePrimitive(LatticeParam(cfg));primitive=np.zeros((15,3,3));primitive[:,:,0]=lattice.lattice_pos_node[::-1];primitive[:,:,1]=lattice.lattice_vel_node[::-1]
    stop=[];signal.signal(signal.SIGTERM,lambda *_:stop.append(True));signal.signal(signal.SIGINT,lambda *_:stop.append(True))
    experts={};started=time.perf_counter();completed=first
    def checkpoint(status):
        for a in arrays.values():a.flush()
        write_json_atomic(output/'progress.json',{'status':status,'completed_samples':completed,'total_samples':len(dataset),'wall_this_process_s':time.perf_counter()-started})
    try:
        checkpoint('running')
        for begin in range(first,len(dataset),16):
            if stop:checkpoint('checkpointed');return
            indices=np.arange(begin,min(begin+16,len(dataset)))
            _,p,r,obs,ids=stack_batch(dataset,indices)
            starts,initials,goals=world_problem(p,r,obs,np.broadcast_to(primitive,(len(indices),15,3,3)),cfg['goal_length'])
            arrays['states'][indices]=np.column_stack([p,r.reshape(-1,9),obs,ids])
            for map_id in np.unique(ids):
                if int(map_id) not in experts:
                    shard=next(s for s in dataset.shards if s['id']==map_id)
                    folder=args.dataset/shard['path'];meta=json.loads((folder/'map.json').read_text())
                    assert sha256_file(folder/'sdf.npy')==meta['sdf_sha256']
                    experts[int(map_id)]=ExpertMap(folder)
                selected=np.flatnonzero(ids==map_id);flat=(selected[:,None]*15+np.arange(15)).reshape(-1)
                expert=experts[int(map_id)]
                base,_=expert.evaluate(starts[flat],initials[flat],goals[flat]);arrays['initial_cost'][indices[selected]]=base.reshape(-1,15)
                for variant in ['scaled_gd50','mma50_evaluations']:
                    ends,costs,diagnostics=expert.optimize(starts[flat],initials[flat],goals[flat],variant)
                    assert np.isfinite(costs).all() and np.isfinite(ends).all()
                    arrays[variant+'_cost'][indices[selected]]=costs.reshape(-1,15)
                    arrays[variant+'_ends_world'][indices[selected]]=ends.reshape(-1,15,3,3)
                    arrays[variant+'_diagnostics'][indices[selected]]=diagnostics.reshape(-1,15,5)
            completed=int(indices[-1])+1;checkpoint('running')
            if completed%256==0 or completed==len(dataset):print(f'EXPERT_CACHE {completed}/{len(dataset)} wall={time.perf_counter()-started:.1f}s',flush=True)
        checkpoint('complete');summary={}
        for variant in ['scaled_gd50','mma50_evaluations']:
            cost=arrays[variant+'_cost'];diag=arrays[variant+'_diagnostics']
            summary[variant]={'average_of15_cost':float(cost.mean()),'average_best_of15_cost':float(cost.min(axis=1).mean()),
                'objective_evaluations_range':[int(diag[:,:,0].min()),int(diag[:,:,0].max())],
                'accepted_update_range':[int(diag[:,:,1].min()),int(diag[:,:,1].max())],
                'cpp_wall_ms_per_sample_mean':float(diag[:,:,4].sum(axis=1).mean()),'nonfinite_evaluations':int(diag[:,:,3].sum())}
        write_json_atomic(output/'result.json',{'status':'complete','scope':config['scope'],'samples':completed,
            'primitive_average_cost':float(arrays['initial_cost'].mean()),'primitive_best_cost':float(arrays['initial_cost'].min(axis=1).mean()),
            'variants':summary,'files_sha256':{name+'.npy':sha256_file(output/(name+'.npy')) for name in arrays}})
    finally:
        for expert in experts.values():expert.close()


if __name__=='__main__':main()
