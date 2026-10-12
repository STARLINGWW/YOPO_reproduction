"""Fine-tune an audited base seed on the DAgger aggregation dataset version.

This run is deliberately kept separate from the formal three-seed training:
it writes into its own run directory, records the base checkpoint hash and the
aggregation dataset hash, never loads official YOPO weights, and never
overwrites the base run. Its result.json is tagged as a fine-tuning experiment
so it cannot be mistaken for a formal 50-epoch seed.
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
ROOT = Path('/workspace')
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import torch
from yopo_repro.io import sha256_file,write_json_atomic
from yopo_repro.policy import build_policy,load_config,MapBank,losses
from yopo_repro.dataset import ForestDataset,stack_batch


def model_hash(policy):
    digest = hashlib.sha256()
    for name,value in sorted(policy.state_dict().items()):
        digest.update(name.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def atomic_torch_save(value,path):
    temporary = path.with_suffix(path.suffix+'.tmp')
    torch.save(value,temporary);temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset',default='/data/isaac_dagger_v1')
    parser.add_argument('--run',required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--epochs',type=int,required=True)
    parser.add_argument('--batch-size',type=int,default=16)
    parser.add_argument('--base-run',default='formal_main_v1_seed0')
    parser.add_argument('--base-checkpoint',default='best_policy.pth')
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--allow-rehearsal',action='store_true',
                        help='Allow a reduced rehearsal dataset (path must contain "rehearsal"); recorded as a rehearsal run')
    args = parser.parse_args()
    dataset = Path(args.dataset).resolve()
    run = ROOT/'checkpoints'/args.run
    base_folder = (ROOT/'checkpoints'/args.base_run).resolve()
    if run.resolve()==base_folder or base_folder in run.resolve().parents:
        raise ValueError('Fine-tuning run must not write into the base run')
    if run.exists():raise FileExistsError('Run directory already exists: %s'%run)
    audit = json.loads((base_folder/'training_audit.json').read_text(encoding='utf-8'))
    if audit['status']!='passed' or audit['epochs']!=50:raise ValueError('Base seed has no passed 50-epoch audit')
    base_checkpoint = (base_folder/args.base_checkpoint).resolve()
    if not base_checkpoint.is_relative_to(base_folder) or not base_checkpoint.is_file():
        raise ValueError('Base checkpoint missing')
    base_sha = sha256_file(base_checkpoint)
    if args.base_checkpoint=='best_policy.pth' and base_sha!=audit['selection']['best_policy_file_sha256']:
        raise ValueError('Base checkpoint is not the audited validation-selected model')
    index = json.loads((dataset/'dataset.json').read_text(encoding='utf-8'))
    if args.allow_rehearsal:
        if 'rehearsal' not in str(dataset).lower():
            raise ValueError('Rehearsal mode requires a dataset path containing "rehearsal"')
        if index['status']!='complete':raise ValueError('Rehearsal dataset is not complete')
    elif index['status']!='complete' or index.get('scale')!='dagger_aggregation':
        raise ValueError('Aggregation dataset is not complete')
    aggregation = json.loads((dataset/'aggregation_manifest.json').read_text(encoding='utf-8'))
    if aggregation['status']!='complete':raise ValueError('Aggregation manifest is not complete')
    policy,profile,cfg = build_policy(device=args.device)
    base_state = torch.load(base_checkpoint,map_location=args.device,weights_only=True)
    policy.load_state_dict(base_state,strict=True)
    initial_hash = model_hash(policy)
    optimizer = torch.optim.Adam(policy.parameters(),lr=profile['optimizer']['learning_rate'])
    train = ForestDataset(dataset,'train',cfg);validation = ForestDataset(dataset,'valid',cfg)
    if min(len(train),len(validation))<args.batch_size:raise ValueError('Insufficient complete batches')
    train_bank = MapBank(dataset,train.shards,cfg);val_bank = MapBank(dataset,validation.shards,cfg)
    config = {'seed':args.seed,'epochs':args.epochs,'batch_size':args.batch_size,'device':args.device,
              'profile':profile,'trajectory':cfg,'dataset_sha256':sha256_file(dataset/'dataset.json'),
              'base_run':args.base_run,'base_checkpoint':args.base_checkpoint,'base_checkpoint_sha256':base_sha,
              'base_initial_model_sha256':audit['selection']['initial_model_tensor_sha256'],
              'train_samples':len(train),'valid_samples':len(validation),'validation_state_seed':0,
              'torch':torch.__version__,'scope':'dagger_aggregation_finetune_not_formal_seed'}
    if args.allow_rehearsal:config['rehearsal'] = True
    run.mkdir(parents=True,exist_ok=False)
    write_json_atomic(run/'run_manifest.json',{**{k:v for k,v in config.items() if not isinstance(v,(dict,))},
        'initialization':'fine-tuned from an audited base checkpoint on base data plus on-policy aggregation frames',
        'official_weights_loaded':False,'dataset_path':str(dataset),'initial_model_sha256':initial_hash,'status':'initialized'})
    atomic_torch_save(policy.state_dict(),run/'initial_policy.pth')
    cursor = {'epoch':0,'batch':0,'step':0,'permutation':None,'sums':[0.,0.,0.],'count':0,'best_val':float('inf')}
    def save(path):
        payload = {'schema':1,'config':config,'cursor':cursor,'model':policy.state_dict(),
                   'optimizer':optimizer.state_dict(),'initial_model_sha256':initial_hash,
                   'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),
                   'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all() if args.device=='cuda' else []}
        atomic_torch_save(payload,path)
    save(run/'latest.pt')
    stop_requested = []
    def stop(signum,frame):stop_requested.append(signum)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    from torch.utils.tensorboard import SummaryWriter
    logger = SummaryWriter(str(run/'tensorboard'))
    started = time.perf_counter();starting_step = cursor['step']
    def progress(status):
        write_json_atomic(run/'progress.json',{'status':status,'epoch_completed':cursor['epoch'],'batch_cursor':cursor['batch'],
            'step':cursor['step'],'target_epochs':args.epochs,'elapsed_this_process_s':time.perf_counter()-started})
    def write_metric(row):
        with (run/'metrics.jsonl').open('a',encoding='utf-8') as file:file.write(json.dumps(row)+'\n')
    try:
        progress('running')
        while cursor['epoch']<args.epochs:
            epoch = cursor['epoch'];train.epoch = epoch;policy.train()
            if cursor['permutation'] is None:
                cursor['permutation'] = np.random.default_rng(np.random.SeedSequence([args.seed,epoch,719])).permutation(len(train))
            total_batches = len(train)//args.batch_size
            while cursor['batch']<total_batches:
                if stop_requested:
                    save(run/'latest.pt');progress('checkpointed');logger.close()
                    print('CHECKPOINTED '+json.dumps({'step':cursor['step'],'epoch':epoch,'batch':cursor['batch']}),flush=True)
                    return
                batch = cursor['batch'];indices = cursor['permutation'][batch*args.batch_size:(batch+1)*args.batch_size]
                depth,pos,rotation,obs,map_id = stack_batch(train,indices)
                optimizer.zero_grad(set_to_none=True)
                total,trajectory,score = losses(policy,torch.from_numpy(depth),pos,rotation,obs,map_id,train_bank,profile)
                if not bool(torch.isfinite(total)):raise FloatingPointError('Nonfinite loss')
                total.backward()
                grad_norm = torch.nn.utils.clip_grad_norm_(policy.parameters(),profile['optimizer']['max_grad_norm'],error_if_nonfinite=True)
                optimizer.step()
                values = [float(x.detach()) for x in (total,trajectory,score)]
                cursor['sums'] = [a+b for a,b in zip(cursor['sums'],values)];cursor['count'] += 1
                cursor['batch'] += 1;cursor['step'] += 1
                if cursor['step']%10==0:
                    row = {'kind':'train_step','step':cursor['step'],'epoch':epoch,'batch':cursor['batch'],
                           'total':values[0],'trajectory':values[1],'score':values[2],'gradient_norm_before_clip':float(grad_norm)}
                    write_metric(row)
                    for name,value in zip(['total','trajectory','score'],values):logger.add_scalar('train/'+name,value,cursor['step'])
                    progress('running');print('TRAIN '+json.dumps(row),flush=True)
            policy.eval();validation_losses = []
            with torch.no_grad():
                for first in range(0,len(validation)-args.batch_size+1,args.batch_size):
                    depth,pos,rotation,obs,map_id = stack_batch(validation,np.arange(first,first+args.batch_size))
                    value = losses(policy,torch.from_numpy(depth),pos,rotation,obs,map_id,val_bank,profile)[0]
                    validation_losses.append(float(value))
            validation_loss = float(np.mean(validation_losses))
            if not np.isfinite(validation_loss):raise FloatingPointError('Nonfinite validation loss')
            row = {'kind':'epoch','epoch':epoch+1,'step':cursor['step'],'train_mean':(np.array(cursor['sums'])/cursor['count']).tolist(),
                   'validation_total':validation_loss,'wall_elapsed_s':time.perf_counter()-started}
            write_metric(row);logger.add_scalar('validation/total',validation_loss,epoch+1)
            if validation_loss<cursor['best_val']:
                cursor['best_val'] = validation_loss;atomic_torch_save(policy.state_dict(),run/'best_policy.pth')
            cursor.update(epoch=epoch+1,batch=0,permutation=None,sums=[0.,0.,0.],count=0)
            save(run/f'epoch_{epoch+1:03d}.pt');save(run/'latest.pt')
            atomic_torch_save(policy.state_dict(),run/f'policy_epoch_{epoch+1:03d}.pth')
            progress('running');print('EPOCH '+json.dumps(row),flush=True)
        progress('complete')
        write_json_atomic(run/'result.json',{'status':'complete','scope':'dagger_aggregation_finetune_not_formal_seed',
            'rehearsal':bool(args.allow_rehearsal),
            'epochs':cursor['epoch'],'steps':cursor['step'],'seed':args.seed,
            'base_run':args.base_run,'base_checkpoint':args.base_checkpoint,'base_checkpoint_sha256':base_sha,
            'base_initial_model_sha256':audit['selection']['initial_model_tensor_sha256'],
            'dataset_sha256':sha256_file(dataset/'dataset.json'),'initial_model_sha256':initial_hash,
            'final_model_sha256':model_hash(policy),'best_validation_total':cursor['best_val'],
            'wall_this_process_s':time.perf_counter()-started,'steps_this_process':cursor['step']-starting_step,
            'official_weights_loaded':False,'writes_into_base_run':False})
    except Exception:
        progress('failed');(run/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:logger.close()


if __name__=='__main__':main()
