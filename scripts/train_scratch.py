"""Deterministic, resumable original-main YOPO training on map-disjoint Isaac data.

New runs always initialize the complete network randomly. Official checkpoints
are never read. Resume accepts only this run's own signed-by-hash configuration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import signal
import sys
import time
import traceback

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
os.environ.setdefault('OMP_NUM_THREADS','4')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import torch
from yopo_repro.io import sha256_file,write_json_atomic
from yopo_repro.policy import build_policy,MapBank,losses
from yopo_repro.dataset import ForestDataset,stack_batch


def model_hash(policy):
    digest=hashlib.sha256()
    for name,value in sorted(policy.state_dict().items()):
        digest.update(name.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def code_hash():
    files=list((ROOT/'src/yopo_repro').glob('*.py'))+[Path(__file__).resolve(),ROOT/'configs/paper_aligned.json']
    files += [ROOT/'external/audit_sources/main/flightpolicy/yopo'/name for name in ['yopo_policy.py','yopo_network.py','resnet.py','primitive_utils.py']]
    digest=hashlib.sha256()
    for path in sorted(files):digest.update(path.relative_to(ROOT).as_posix().encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def atomic_torch_save(value,path):
    temporary=path.with_suffix(path.suffix+'.tmp')
    torch.save(value,temporary);temporary.replace(path)


def validate_data(root):
    index=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
    assert index['status']=='complete'
    seeds={};ids=set()
    for shard in index['shards']:
        assert shard['id'] not in ids;ids.add(shard['id'])
        if shard['map_seed'] in seeds:raise ValueError('Map seed is duplicated across shards/splits')
        seeds[shard['map_seed']]=shard['split']
        folder=root/shard['path']
        assert sha256_file(folder/'manifest.json')==shard['manifest_sha256']
        assert sha256_file(folder/'map.json')==shard['map_sha256']
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        maps=json.loads((folder/'map.json').read_text(encoding='utf-8'))
        assert manifest['status']=='complete' and manifest['completed_samples']==shard['samples']
        assert sha256_file(folder/'depth_m.npy')==manifest['depth_sha256']
        assert sha256_file(folder/'poses.npz')==manifest['poses_sha256']
        assert sha256_file(folder/'sdf.npy')==maps['sdf_sha256']
    return index


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--run',required=True)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--epochs',type=int,default=50)
    parser.add_argument('--batch-size',type=int,default=16)
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--stop-after-steps',type=int)
    parser.add_argument('--checkpoint-steps',type=int,default=250)
    args=parser.parse_args()
    dataset=args.dataset.resolve();run=(ROOT/'checkpoints'/args.run).resolve()
    if not run.is_relative_to(ROOT/'checkpoints'):raise ValueError('Run must be inside checkpoints')
    if args.epochs<1 or args.batch_size<1:raise ValueError('Invalid training size')
    if args.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
    if not args.resume:run.mkdir(parents=True,exist_ok=False)
    elif not (run/'latest.pt').exists():raise FileNotFoundError('No resumable checkpoint')
    data_index=validate_data(dataset)
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)
    policy,profile,cfg=build_policy(args.device)
    optimizer=policy.optimizer
    train=ForestDataset(dataset,'train',cfg,args.seed)
    validation=ForestDataset(dataset,'valid',cfg,seed=0)
    train_bank=MapBank(dataset,train.shards,cfg)
    val_bank=MapBank(dataset,validation.shards,cfg)
    if min(len(train),len(validation))<args.batch_size:raise ValueError('Insufficient complete batches')
    config={'seed':args.seed,'epochs':args.epochs,'batch_size':args.batch_size,'device':args.device,
            'profile':profile,'trajectory':cfg,'dataset_sha256':sha256_file(dataset/'dataset.json'),
            'code_sha256':code_hash(),'torch':torch.__version__,'train_samples':len(train),'valid_samples':len(validation),
            'validation_state_seed':0}
    cursor={'epoch':0,'batch':0,'step':0,'permutation':None,'sums':[0.,0.,0.],'count':0,'best_val':float('inf')}
    initial_hash=model_hash(policy)
    def save(path):
        payload={'schema':1,'config':config,'cursor':cursor,'model':policy.state_dict(),'optimizer':optimizer.state_dict(),
                 'initial_model_sha256':initial_hash,'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),
                 'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all() if args.device=='cuda' else []}
        atomic_torch_save(payload,path)
    if args.resume:
        # Only a checkpoint produced locally inside this run is accepted.
        checkpoint=torch.load(run/'latest.pt',map_location=args.device,weights_only=False)
        if checkpoint['config']!=config:raise ValueError('Resume code/config/data/version mismatch')
        policy.load_state_dict(checkpoint['model'],strict=True);optimizer.load_state_dict(checkpoint['optimizer'])
        cursor=checkpoint['cursor'];initial_hash=checkpoint['initial_model_sha256']
        random.setstate(checkpoint['python_rng']);np.random.set_state(checkpoint['numpy_rng'])
        torch.set_rng_state(checkpoint['torch_rng'].cpu())
        if args.device=='cuda':torch.cuda.set_rng_state_all([x.cpu() for x in checkpoint['cuda_rng']])
    else:
        write_json_atomic(run/'run_manifest.json',{**config,'initial_model_sha256':initial_hash,
                          'initialization':'random entire network, pretrained=False; official weights never loaded',
                          'dataset_path':str(dataset),'status':'initialized'})
        atomic_torch_save(policy.state_dict(),run/'initial_policy.pth');save(run/'latest.pt')
    stop_requested=[]
    def stop(signum,frame):stop_requested.append(signum)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    from torch.utils.tensorboard import SummaryWriter
    logger=SummaryWriter(str(run/'tensorboard'))
    started=time.perf_counter();starting_step=cursor['step']
    def progress(status):
        write_json_atomic(run/'progress.json',{'status':status,'epoch_completed':cursor['epoch'],'batch_cursor':cursor['batch'],
                          'step':cursor['step'],'target_epochs':args.epochs,'elapsed_this_process_s':time.perf_counter()-started})
    def write_metric(row):
        with (run/'metrics.jsonl').open('a',encoding='utf-8') as file:file.write(json.dumps(row)+'\n')
    try:
        progress('running')
        while cursor['epoch']<args.epochs:
            epoch=cursor['epoch'];train.epoch=epoch;policy.train()
            if cursor['permutation'] is None:
                cursor['permutation']=np.random.default_rng(np.random.SeedSequence([args.seed,epoch,719])).permutation(len(train))
            total_batches=len(train)//args.batch_size
            while cursor['batch']<total_batches:
                if stop_requested or (args.stop_after_steps is not None and cursor['step']>=args.stop_after_steps):
                    save(run/'latest.pt');progress('checkpointed');logger.close()
                    print('CHECKPOINTED '+json.dumps({'step':cursor['step'],'epoch':epoch,'batch':cursor['batch']}),flush=True);return
                batch=cursor['batch'];indices=cursor['permutation'][batch*args.batch_size:(batch+1)*args.batch_size]
                depth,pos,rotation,obs,map_id=stack_batch(train,indices)
                optimizer.zero_grad(set_to_none=True)
                total,trajectory,score=losses(policy,torch.from_numpy(depth),pos,rotation,obs,map_id,train_bank,profile)
                if not bool(torch.isfinite(total)):raise FloatingPointError('Nonfinite loss')
                total.backward()
                grad_norm=torch.nn.utils.clip_grad_norm_(policy.parameters(),profile['optimizer']['max_grad_norm'],error_if_nonfinite=True)
                optimizer.step()
                values=[float(x.detach()) for x in (total,trajectory,score)]
                cursor['sums']=[a+b for a,b in zip(cursor['sums'],values)];cursor['count']+=1
                cursor['batch']+=1;cursor['step']+=1
                if cursor['step']%10==0:
                    row={'kind':'train_step','step':cursor['step'],'epoch':epoch,'batch':cursor['batch'],
                         'total':values[0],'trajectory':values[1],'score':values[2],'gradient_norm_before_clip':float(grad_norm)}
                    write_metric(row)
                    for name,value in zip(['total','trajectory','score'],values):logger.add_scalar('train/'+name,value,cursor['step'])
                    progress('running')
                    print('TRAIN '+json.dumps(row),flush=True)
                if args.checkpoint_steps and cursor['step']%args.checkpoint_steps==0:save(run/'latest.pt')
            policy.eval();validation_losses=[]
            with torch.no_grad():
                for first in range(0,len(validation)-args.batch_size+1,args.batch_size):
                    depth,pos,rotation,obs,map_id=stack_batch(validation,np.arange(first,first+args.batch_size))
                    value=losses(policy,torch.from_numpy(depth),pos,rotation,obs,map_id,val_bank,profile)[0]
                    validation_losses.append(float(value))
            validation_loss=float(np.mean(validation_losses))
            if not np.isfinite(validation_loss):raise FloatingPointError('Nonfinite validation loss')
            row={'kind':'epoch','epoch':epoch+1,'step':cursor['step'],'train_mean':(np.array(cursor['sums'])/cursor['count']).tolist(),
                 'validation_total':validation_loss,'wall_elapsed_s':time.perf_counter()-started}
            write_metric(row);logger.add_scalar('validation/total',validation_loss,epoch+1)
            if validation_loss<cursor['best_val']:
                cursor['best_val']=validation_loss;atomic_torch_save(policy.state_dict(),run/'best_policy.pth')
            cursor.update(epoch=epoch+1,batch=0,permutation=None,sums=[0.,0.,0.],count=0)
            save(run/f'epoch_{epoch+1:03d}.pt');save(run/'latest.pt')
            atomic_torch_save(policy.state_dict(),run/f'policy_epoch_{epoch+1:03d}.pth')
            progress('running');print('EPOCH '+json.dumps(row),flush=True)
        progress('complete')
        write_json_atomic(run/'result.json',{'status':'complete','epochs':cursor['epoch'],'steps':cursor['step'],
                         'initial_model_sha256':initial_hash,'final_model_sha256':model_hash(policy),
                         'best_validation_total':cursor['best_val'],'wall_this_process_s':time.perf_counter()-started,
                         'steps_this_process':cursor['step']-starting_step,'official_weights_loaded':False})
    except Exception:
        progress('failed');(run/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:logger.close()


if __name__=='__main__':main()
