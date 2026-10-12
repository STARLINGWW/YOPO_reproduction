"""Compare trained/random-init YOPO networks against the frozen expert cache.

The expert cache in artifacts/expert/<run>/ was produced from the original
unchanged-main GradTrajOptimizer on the 10000 independent test samples with a
fixed candidate order. This script runs the network on exactly the same samples
(alignment is asserted against states.npy before any statistic is computed),
maps the 15 predicted candidates into the world frame with the same
body-to-world convention the training loss uses, and scores them with the same
C++ objective. Nothing here tunes on the test split.
"""
from pathlib import Path
import argparse
import json
import sys
import time
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic
from yopo_repro.policy import build_policy,load_config,prepare_observation,decode_all
from yopo_repro.dataset import ForestDataset,stack_batch
from yopo_expert.core import ExpertMap


def network_ends(policy,dataset,indices,device):
    depth,pos,rotation,obs,identifiers = stack_batch(dataset,indices)
    prepared = torch.from_numpy(prepare_observation(obs,policy)).to(device)
    with torch.no_grad():
        started = time.perf_counter()
        prediction = policy(torch.from_numpy(depth).to(device),prepared)
        forward_s = time.perf_counter()-started
        ends = decode_all(policy,prediction).cpu().numpy().reshape(len(indices),15,3,3)
        scores = prediction[:,9].reshape(len(indices),15).cpu().numpy()
    return ends,scores,pos,rotation,obs,identifiers,forward_s


def world_frame(ends,pos,rotation,obs,goal_length):
    start = np.empty((len(pos),3,3));start[:,:,0] = pos
    start[:,:,1] = np.einsum('bij,bj->bi',rotation,obs[:,:3])
    start[:,:,2] = np.einsum('bij,bj->bi',rotation,obs[:,3:6])
    goal = pos+np.einsum('bij,bj->bi',rotation,goal_length*obs[:,6:9])
    end_world = np.einsum('bij,bmjk->bmik',rotation,ends)
    end_world[:,:,:,0] += pos[:,None,:]
    return start,end_world,goal


def running(values):
    values = np.asarray(values,float)
    if not len(values):return {'n':0,'mean':None,'p50':None,'p95':None,'max':None}
    return {'n':int(len(values)),'mean':float(values.mean()),'p50':float(np.percentile(values,50)),
            'p95':float(np.percentile(values,95)),'max':float(values.max())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,default=Path('/data/isaac_full_v1'))
    parser.add_argument('--expert-cache',type=Path,default=ROOT/'artifacts/expert/formal_test_v1')
    parser.add_argument('--checkpoint')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--batch-size',type=int,default=16)
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--label',help='Evidence label for this network source, e.g. trained_seed1')
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    dataset_path = args.dataset.resolve();cache = args.expert_cache.resolve()
    validation = json.loads((dataset_path/'validation.json').read_text(encoding='utf-8'))
    if validation['status']!='passed' or validation['counts']['test']!=10000:
        raise ValueError('Independent test split is not validated')
    cache_result = json.loads((cache/'result.json').read_text(encoding='utf-8'))
    if cache_result['status']!='complete' or cache_result['samples']!=10000:
        raise ValueError('Expert cache is not complete')
    profile,cfg = load_config()
    torch.manual_seed(args.seed)
    policy,_,_ = build_policy(device=args.device)
    checkpoint_evidence = {'kind':'random_initial','path':None,'sha256':None,
                           'initialization':'fresh build_policy from scratch, no weights loaded (official or scratch)'}
    if args.checkpoint:
        path = Path(args.checkpoint)
        if not path.is_absolute():path = ROOT/path
        if not path.is_file():raise FileNotFoundError(str(path))
        state = torch.load(path,map_location=args.device,weights_only=True)
        policy.load_state_dict(state,strict=True)
        checkpoint_evidence = {'kind':'trained','path':str(path.relative_to(ROOT).as_posix()),
                               'sha256':sha256_file(path),'initialization':'locally scratch-trained weights'}
    if args.label:checkpoint_evidence['kind'] = args.label
    policy.eval()
    dataset = ForestDataset(dataset_path,'test',cfg,seed=0)
    total = len(dataset) if not args.limit else min(args.limit,len(dataset))
    states = np.load(cache/'states.npy',mmap_mode='r')
    expert_costs = {name:np.load(cache/(name+'_cost.npy'),mmap_mode='r') for name in ['scaled_gd50','mma50_evaluations']}
    expert_ends = {name:np.load(cache/(name+'_ends_world.npy'),mmap_mode='r') for name in ['scaled_gd50','mma50_evaluations']}
    network_costs = np.full((total,15),np.nan);network_scores = np.full((total,15),np.nan)
    network_ends_world = np.full((total,15,3,3),np.nan)
    forward_seconds = 0.;total_seconds = 0.;alignment_error = 0.
    start_time = time.perf_counter()
    experts = {}
    try:
        for begin in range(0,total,args.batch_size):
            indices = np.arange(begin,min(begin+args.batch_size,total))
            depth,pos,rotation,obs,identifiers = stack_batch(dataset,indices)
            recorded = states[indices]
            alignment = np.concatenate([pos,rotation.reshape(-1,9),obs,identifiers[:,None].astype(float)],axis=1)
            alignment_error = max(alignment_error,float(np.max(np.abs(alignment-recorded))))
            if alignment_error>1e-9:raise ValueError('Sample alignment with the expert cache failed')
            ends,scores,pos,rotation,obs,identifiers,forward = network_ends(policy,dataset,indices,args.device)
            forward_seconds += forward
            starts,end_world,goal = world_frame(ends,pos,rotation,obs,cfg['goal_length'])
            for identifier in np.unique(identifiers):
                if int(identifier) not in experts:
                    shard = next(s for s in dataset.shards if s['id']==int(identifier))
                    folder = dataset_path/shard['path']
                    meta = json.loads((folder/'map.json').read_text(encoding='utf-8'))
                    if sha256_file(folder/'sdf.npy')!=meta['sdf_sha256']:raise ValueError('Map SDF hash changed')
                    experts[int(identifier)] = ExpertMap(folder)
                selected = np.flatnonzero(identifiers==identifier)
                count = len(selected)
                repeated_starts = np.repeat(starts[selected],15,axis=0)
                repeated_goals = np.repeat(goal[selected],15,axis=0)
                costs,_ = experts[int(identifier)].evaluate(repeated_starts,end_world[selected].reshape(-1,3,3),repeated_goals)
                network_costs[indices[selected]] = costs.reshape(count,15)
            network_scores[indices] = scores;network_ends_world[indices] = end_world
            if (begin//args.batch_size)%20==0:
                print('COMPARE %d/%d wall=%.1fs'%(min(begin+args.batch_size,total),total,time.perf_counter()-start_time),flush=True)
    finally:
        for expert in experts.values():expert.close()
    total_seconds = time.perf_counter()-start_time
    expert_best = {name:np.argmin(np.asarray(expert_costs[name][:total]),axis=1) for name in expert_costs}
    network_best = np.argmin(network_costs,axis=1);network_score_best = np.argmin(network_scores,axis=1)
    selected_positions = network_ends_world[np.arange(total),network_best,:,0]
    per_variant = {}
    for name in expert_costs:
        expert_end_positions = np.asarray(expert_ends[name][:total])[np.arange(total),expert_best[name],:,0]
        chosen_error = np.linalg.norm(selected_positions-expert_end_positions,axis=1)
        all_error = np.linalg.norm(network_ends_world[...,0]-np.asarray(expert_ends[name][:total])[...,0],axis=-1)
        per_variant[name] = {
            'expert_mean_of15_cost':float(np.asarray(expert_costs[name][:total]).mean()),
            'expert_mean_best_of15_cost':float(np.asarray(expert_costs[name][:total]).min(axis=1).mean()),
            'network_cost_of_predictions_mean_of15':float(network_costs.mean()),
            'network_cost_of_predictions_mean_best_of15':float(network_costs.min(axis=1).mean()),
            'cost_argmin_agreement_fraction':float(np.mean(network_best==expert_best[name])),
            'score_head_argmin_agreement_fraction':float(np.mean(network_score_best==expert_best[name])),
            'selected_position_error_m':running(chosen_error),
            'per_candidate_position_error_m':running(all_error.reshape(-1))}
    payload = {'status':'complete','scope':'Expert comparison on independent offline test maps with an explicitly '
               'reconstructed expert solver setting; no test-based tuning.','samples':int(total),
               'dataset_sha256':sha256_file(dataset_path/'dataset.json'),
               'expert_cache':{'path':str(cache.relative_to(ROOT).as_posix()),
                               'result_sha256':sha256_file(cache/'result.json'),
                               'variants':cache_result['variants'],'scope':cache_result['scope']},
               'checkpoint':checkpoint_evidence,
               'sample_alignment_max_abs_error':alignment_error,
               'expert':{name:{'mean_of15_cost':per_variant[name]['expert_mean_of15_cost'],
                               'mean_best_of15_cost':per_variant[name]['expert_mean_best_of15_cost'],
                               'cpp_wall_ms_per_sample':cache_result['variants'][name]['cpp_wall_ms_per_sample_mean'],
                               'objective_evaluations_mean':float(np.mean([cache_result['variants'][name]['objective_evaluations_range'][0],
                                                                            cache_result['variants'][name]['objective_evaluations_range'][1]]))}
                        for name in expert_costs},
               'network_vs_expert':per_variant,
               'network_cost_of_predictions':running(network_costs.reshape(-1)),
               'score_head_cost_gap':running(network_scores.reshape(-1)-network_costs.reshape(-1)),
               'timing':{'network_inference_ms_per_sample':1000*forward_seconds/max(total,1),
                         'network_inference_scope':'policy forward only, CPU, batch %d, threads %d'%(args.batch_size,args.threads),
                         'wall_ms_per_sample_including_expert_evaluation':1000*total_seconds/max(total,1)},
               'notes':['The network is scored with the same original C++ objective used for the expert cache.',
                        'The expert driver in the public main repository is not published; the variants are explicit reconstructions.',
                        'Network inference timing is CPU-only and is not a GPU latency claim.']}
    output = args.output or (ROOT/'artifacts/expert'/('network_comparison_%s%s.json'%(checkpoint_evidence['kind'],
               '' if not args.limit else '_limit%d'%args.limit)))
    output = Path(output)
    for key in ['baselines']:
        payload.setdefault(key,{})
    variant_name = checkpoint_evidence['kind']
    reference = per_variant['scaled_gd50']
    payload['baselines'][variant_name] = {'mean_of15_cost':reference['network_cost_of_predictions_mean_of15'],
        'mean_best_of15_cost':reference['network_cost_of_predictions_mean_best_of15'],
        'position_error_vs_expert_m':{'mean':reference['selected_position_error_m']['mean'],
                                      'p95':reference['selected_position_error_m']['p95']}}
    payload['network_vs_expert']['selected_candidate_matches_expert_best_fraction'] = \
        per_variant['scaled_gd50']['cost_argmin_agreement_fraction']
    payload['network_vs_expert']['position_error_m'] = per_variant['scaled_gd50']['selected_position_error_m']
    payload['network_vs_expert']['velocity_error_mps'] = {}
    payload['network_vs_expert']['acceleration_error_mps2'] = {}
    for name in expert_costs:
        expert_final = np.asarray(expert_ends[name][:total])
        chosen = expert_best[name]
        payload['network_vs_expert']['velocity_error_mps'][name] = running(np.linalg.norm(
            network_ends_world[np.arange(total),network_best,:,1]-expert_final[np.arange(total),chosen,:,1],axis=1))
        payload['network_vs_expert']['acceleration_error_mps2'][name] = running(np.linalg.norm(
            network_ends_world[np.arange(total),network_best,:,2]-expert_final[np.arange(total),chosen,:,2],axis=1))
    write_json_atomic(output,payload)
    print(json.dumps({k:payload[k] for k in ['status','samples','checkpoint','sample_alignment_max_abs_error','network_cost_of_predictions','timing']},indent=2)[:1500])
    print(str(output))


if __name__=='__main__':main()
