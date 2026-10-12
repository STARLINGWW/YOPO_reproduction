"""Conversion parity; CPU by default while formal YOPO training owns the GPU."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
import torch
ROOT=Path('/workspace');sys.path.insert(0,str(ROOT/'src'))
from agile_runtime.torch_network import AgileNetwork
parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cpu','cuda'],default='cpu');args=parser.parse_args()
torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
folder=ROOT/'artifacts/agile_autonomy/torch_export_v1';model=AgileNetwork(folder).to(args.device).eval()
data=np.load(folder/'parity_inputs_outputs.npz');outputs=[];times=[]
with torch.inference_mode():
    for i in range(len(data['imu'])):
        depth=torch.from_numpy(data['depth'][i:i+1]).to(args.device);imu=torch.from_numpy(data['imu'][i:i+1]).to(args.device)
        if args.device=='cuda':torch.cuda.synchronize()
        started=time.perf_counter();value=model(depth,imu)
        if args.device=='cuda':torch.cuda.synchronize()
        times.append((time.perf_counter()-started)*1000);outputs.append(value.cpu().numpy())
actual=np.concatenate(outputs);reference=data['outputs'];error=np.abs(actual-reference)
order_equal=bool(np.array_equal(np.abs(actual[:,:,0]).argsort(1),np.abs(reference[:,:,0]).argsort(1)))
def masks(values):
    scores=np.sort(np.abs(values[:,:,0]),axis=1)
    with np.errstate(divide='ignore',invalid='ignore'):mask=scores[:,0:1]/scores>.9
    mask[:,0]=True;return mask
mask_equal=bool(np.array_equal(masks(actual),masks(reference)))
passed=bool(np.allclose(actual,reference,rtol=1e-4,atol=1e-4) and order_equal and mask_equal)
original_path=folder/'tf24_original_outputs.npy'
original_comparison=None
if original_path.is_file():
    original=np.load(original_path);original_error=np.abs(actual-original)
    original_order=bool(np.array_equal(np.abs(actual[:,:,0]).argsort(1),np.abs(original[:,:,0]).argsort(1)))
    original_mask=bool(np.array_equal(masks(actual),masks(original)))
    original_passed=bool(np.allclose(actual,original,rtol=1e-4,atol=1e-4) and original_order and original_mask)
    passed=passed and original_passed
    original_comparison={'status':'passed' if original_passed else 'failed','max_absolute_error':float(original_error.max()),
        'mean_absolute_error':float(original_error.mean()),'mode_order_equal':original_order,'acceptance_masks_equal':original_mask}
report={'status':'passed' if passed else 'failed','scope':'Official Agile network Keras2.15 -> PyTorch conversion; original TF2.4 crosscheck remains separate',
    'device':args.device,'torch':torch.__version__,'cases':len(actual),'max_absolute_error':float(error.max()),
    'mean_absolute_error':float(error.mean()),'all_absolute_score_mode_orders_equal':order_equal,'all_0_9_acceptance_masks_equal':mask_equal,
    'network_ms':times,'checkpoint_sha256':model.manifest['source_checkpoint_sha256'],
    'tf32_enabled':False,'mixed_precision':False,'all_original_variables_exported':model.manifest['variable_count']}
report['original_tf24_comparison']=original_comparison
np.save(folder/f'torch_{args.device}_outputs.npy',actual)
(folder/f'torch_{args.device}_parity.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report));assert passed,'Agile conversion parity failed'
