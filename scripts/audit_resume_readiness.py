from pathlib import Path
import argparse,hashlib,importlib.util,json
import torch
ROOT=Path('/workspace')
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--min-epoch',type=int,default=2);args=parser.parse_args()
folder=ROOT/'checkpoints'/args.run
progress=json.loads((folder/'progress.json').read_text());manifest=json.loads((folder/'run_manifest.json').read_text())
checkpoint=torch.load(folder/'latest.pt',map_location='cpu',weights_only=False)
spec=importlib.util.spec_from_file_location('scratch_training',ROOT/'scripts/train_scratch.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert progress['status']=='checkpointed'
assert checkpoint['cursor']['epoch']>=args.min_epoch and checkpoint['cursor']['step']==progress['step']
assert checkpoint['config']['code_sha256']==module.code_hash()
assert checkpoint['initial_model_sha256']==manifest['initial_model_sha256']
assert checkpoint['optimizer']['state'] and checkpoint['cuda_rng']
assert all(torch.isfinite(v).all() for v in checkpoint['model'].values())
report={'status':'passed','scope':'Graceful formal-training checkpoint for serial native-GPU validation window; training not complete',
        'run':args.run,'epoch_completed':progress['epoch_completed'],'step':progress['step'],
        'code_sha256':checkpoint['config']['code_sha256'],
        'checkpoint_sha256':hashlib.sha256((folder/'latest.pt').read_bytes()).hexdigest()}
(ROOT/'artifacts/environment/formal_checkpoint_window.json').write_text(json.dumps(report,indent=2)+'\n')
history=ROOT/'artifacts/environment/checkpoint_windows';history.mkdir(exist_ok=True)
(history/f'{args.run}_step{progress["step"]}.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
