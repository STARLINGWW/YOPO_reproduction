"""Compare interrupted/resumed training against a separate uninterrupted run."""
from pathlib import Path
import argparse
import json
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--reference',default='resume_reference')
parser.add_argument('--resumed',default='resume_split')
args=parser.parse_args()
a=torch.load(ROOT/'checkpoints'/args.reference/'latest.pt',map_location='cpu',weights_only=False)
b=torch.load(ROOT/'checkpoints'/args.resumed/'latest.pt',map_location='cpu',weights_only=False)
differences=[]
def compare(x,y,path):
    if isinstance(x,torch.Tensor):
        if not isinstance(y,torch.Tensor) or not torch.equal(x,y):differences.append(path)
    elif isinstance(x,np.ndarray):
        if not isinstance(y,np.ndarray) or not np.array_equal(x,y):differences.append(path)
    elif isinstance(x,dict):
        if x.keys()!=y.keys():differences.append(path+'.keys');return
        for k in x:compare(x[k],y[k],path+'.'+str(k))
    elif isinstance(x,(list,tuple)):
        if len(x)!=len(y):differences.append(path+'.length');return
        for i,(xx,yy) in enumerate(zip(x,y)):compare(xx,yy,path+f'[{i}]')
    elif x!=y:differences.append(path)
for key in ['config','cursor','initial_model_sha256','model','optimizer','python_rng','numpy_rng','torch_rng','cuda_rng']:
    compare(a[key],b[key],key)
report={'status':'passed' if not differences else 'failed','reference':args.reference,'resumed':args.resumed,
        'steps':a['cursor']['step'],'completed_epochs':a['cursor']['epoch'],'batch_cursor':a['cursor']['batch'],
        'model_tensor_count':len(a['model']),'bitwise_equal':not differences,'differences':differences,
        'scope':'model, optimizer, permutation/cursor and all RNG states; includes an epoch boundary and validation'}
(ROOT/'artifacts/environment/resume_equivalence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(bool(differences))
