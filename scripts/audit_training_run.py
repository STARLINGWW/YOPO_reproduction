"""Strict completion audit for one formal seed, independent of video/demo results."""
from pathlib import Path
import argparse
import json
import torch
from training_audit_utils import state_hash,verify_model_selection

ROOT=Path('/workspace')
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--seed',type=int,required=True)
args=parser.parse_args();folder=ROOT/'checkpoints'/args.run
result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
manifest=json.loads((folder/'run_manifest.json').read_text(encoding='utf-8'))
checkpoint=torch.load(folder/'latest.pt',map_location='cpu',weights_only=False)
assert result['status']=='complete' and result['epochs']==50 and result['steps']==312500
assert result['official_weights_loaded'] is False
assert manifest['seed']==args.seed and manifest['train_samples']==100000 and manifest['valid_samples']==10000
assert manifest['initialization'].startswith('random entire network')
assert result['initial_model_sha256']!=result['final_model_sha256']
assert checkpoint['cursor']['epoch']==50 and checkpoint['cursor']['step']==312500
assert checkpoint['config']=={k:v for k,v in manifest.items() if k in checkpoint['config']}
for value in checkpoint['model'].values():assert bool(torch.isfinite(value).all())
assert state_hash(checkpoint['model'])==result['final_model_sha256']
assert checkpoint['initial_model_sha256']==manifest['initial_model_sha256']==result['initial_model_sha256']
assert checkpoint['config']['batch_size']==16 and checkpoint['config']['epochs']==50
assert all(not value.is_floating_point() or value.dtype==torch.float32 for value in checkpoint['model'].values())
selection=verify_model_selection(folder,50)
assert selection['best_validation_total']==result['best_validation_total']
assert checkpoint['cursor']['best_val']==selection['best_validation_total']
del checkpoint
epoch_evidence=[]
for epoch in range(1,51):
    assert (folder/f'epoch_{epoch:03d}.pt').is_file() and (folder/f'policy_epoch_{epoch:03d}.pth').is_file()
    saved=torch.load(folder/f'epoch_{epoch:03d}.pt',map_location='cpu',weights_only=False)
    assert saved['cursor']['epoch']==epoch and saved['cursor']['step']==epoch*6250
    assert saved['cursor']['batch']==0 and saved['cursor']['permutation'] is None
    assert saved['config']['seed']==args.seed and saved['initial_model_sha256']==manifest['initial_model_sha256']
    assert saved['config']=={k:v for k,v in manifest.items() if k in saved['config']}
    assert all(torch.isfinite(value).all() for value in saved['model'].values())
    assert saved['optimizer']['state'] and saved['optimizer']['param_groups'][0]['lr']==1.5e-4
    assert saved['python_rng'] and saved['numpy_rng'] and saved['torch_rng'].numel()>0 and saved['cuda_rng']
    for state in saved['optimizer']['state'].values():
        assert int(state['step'])==epoch*6250
        assert torch.isfinite(state['exp_avg']).all() and torch.isfinite(state['exp_avg_sq']).all()
    epoch_hash=state_hash(saved['model']);del saved
    raw=torch.load(folder/f'policy_epoch_{epoch:03d}.pth',map_location='cpu',weights_only=True)
    assert epoch_hash==state_hash(raw), 'Exported policy does not match full checkpoint'
    del raw
    epoch_evidence.append({'epoch':epoch,'model_tensor_sha256':epoch_hash})
report={'status':'passed','run':args.run,'seed':args.seed,'epochs':50,'steps':312500,
        'selection':selection,'every_epoch_state_read_back':epoch_evidence,
        'scope':'formal training provenance/checkpoints/finite weights only; closed-loop and paper benchmarks remain separate'}
(folder/'training_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
