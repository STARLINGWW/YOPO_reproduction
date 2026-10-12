"""Verify complete official Agile Autonomy checkpoint restore on Ubuntu22.04."""
from pathlib import Path
import importlib.util
from types import SimpleNamespace
import hashlib
import json
import os
import time
import numpy as np
import tensorflow as tf
ROOT=Path('/workspace')


def main():
    tf.config.set_visible_devices([], 'GPU')
    config=SimpleNamespace(img_height=224,img_width=224,use_rgb=False,use_depth=True,
        freeze_backbone=False,modes=3,predict_state_number=[],out_seq_len=10,state_dim=3,
        seq_len=1,use_position=False,use_attitude=True)
    path=ROOT/'vendor/agile_ros2/nets.py'
    spec=importlib.util.spec_from_file_location('agile_compat_nets',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    model=module.create_network(config)
    rng=np.random.default_rng(2026)
    inputs={'depth':rng.uniform(0,250,(4,1,224,224,3)).astype(np.float32),
            'imu':rng.normal(size=(4,1,21)).astype(np.float32)}
    inputs['imu'][:,:,3:12]=np.eye(3).reshape(1,1,9)
    model({k:v[:1] for k,v in inputs.items()},training=False)
    ckpt=ROOT/'external/agile_autonomy/planner_learning/models/ckpt-50'
    restore=tf.train.Checkpoint(net=model).restore(str(ckpt))
    restore.assert_existing_objects_matched()
    restore.expect_partial() # optimizer/epoch slots are irrelevant for inference.
    before=[w.numpy().copy() for w in model.weights]
    results=[];times=[]
    for i in range(4):
        t=time.perf_counter();result=model({k:v[i:i+1] for k,v in inputs.items()},training=False).numpy()
        times.append((time.perf_counter()-t)*1000);results.append(result)
    results=np.concatenate(results)
    assert results.shape==(4,3,31) and np.isfinite(results).all()
    assert all(np.array_equal(a,w.numpy()) for a,w in zip(before,model.weights)), 'Inference changed BN/weights'
    out=ROOT/'artifacts/agile_autonomy';out.mkdir(exist_ok=True)
    np.savez(out/'tf215_parity_inputs_outputs.npz',**inputs,outputs=results)
    manifest={'status':'restore_and_finite_inference_passed_original_tf24_parity_pending',
        'tensorflow':tf.__version__,'keras':__import__('keras').__version__,'device':'CPU',
        'checkpoint':'official Agile Autonomy ckpt-50','yopo_weights_used':False,
        'checkpoint_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ckpt.parent.glob('ckpt-50.*')},
        'network_weights':len(model.weights),'all_network_variables_restored':True,
        'ordered_weight_sha256':[hashlib.sha256(w.numpy().tobytes()).hexdigest() for w in model.weights],
        'inference_ms':times,'output_shape':list(results.shape),
        'scope':'baseline inference compatibility only; ROS2/full trajectory backend and TF2.4 comparison pending'}
    (out/'tf215_probe.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)


if __name__=='__main__':main()
