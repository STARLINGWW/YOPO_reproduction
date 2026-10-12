"""Run pinned original TF2.4 architecture/checkpoint on the same TF2.15 inputs."""
from pathlib import Path
from types import SimpleNamespace,ModuleType
import hashlib
import json
import argparse
import numpy as np
import tensorflow as tf
ROOT=Path('/workspace')
output=ROOT/'artifacts/agile_autonomy'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',type=Path,default=output/'tf215_parity_inputs_outputs.npz')
    parser.add_argument('--report-directory',type=Path,default=output);args=parser.parse_args()
    report_directory=args.report_directory.resolve()
    if ROOT not in report_directory.parents:raise ValueError('Report must remain in the project')
    report_directory.mkdir(parents=True,exist_ok=True)
    assert tf.__version__=='2.4.0'
    tf.config.set_visible_devices([], 'GPU')
    source=ROOT/'external/agile_autonomy/planner_learning/src/PlannerLearning/models/nets.py'
    # No architecture/API patch in the reference. Initializer is immaterial:
    # strict restore verifies every network variable before comparison.
    code=source.read_text().replace("weights='imagenet'",'weights=None')
    module=ModuleType('original_tf24_nets');exec(compile(code,str(source),'exec'),module.__dict__)
    config=SimpleNamespace(img_height=224,img_width=224,use_rgb=False,use_depth=True,
        freeze_backbone=False,modes=3,predict_state_number=[],out_seq_len=10,state_dim=3,
        seq_len=1,use_position=False,use_attitude=True)
    model=module.create_network(config)
    data=np.load(args.fixture)
    model({k:data[k][:1] for k in ['depth','imu']},training=False)
    checkpoint=ROOT/'external/agile_autonomy/planner_learning/models/ckpt-50'
    restore=tf.train.Checkpoint(net=model).restore(str(checkpoint))
    restore.assert_existing_objects_matched();restore.expect_partial()
    target_manifest=json.loads((output/'tf215_probe.json').read_text())
    weight_hashes=[hashlib.sha256(w.numpy().tobytes()).hexdigest() for w in model.weights]
    weight_equal=weight_hashes==target_manifest['ordered_weight_sha256']
    assert weight_equal,'Restored variable arrays differ across framework versions'
    results=np.concatenate([model({k:data[k][i:i+1] for k in ['depth','imu']},training=False).numpy()
                            for i in range(len(data['imu']))])
    reference=data['outputs'];error=np.abs(results-reference)
    order_equal=bool(np.array_equal(np.abs(results[:,:,0]).argsort(1),np.abs(reference[:,:,0]).argsort(1)))
    passed=bool(weight_equal and order_equal and np.allclose(results,reference,rtol=1e-4,atol=1e-4))
    np.save(report_directory/'tf24_original_outputs.npy',results)
    record={'status':'passed' if passed else 'failed','reference_tensorflow':tf.__version__,
        'target_tensorflow':'2.15.1','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'ordered_network_weight_arrays_bitwise_equal':weight_equal,'network_weight_count':len(weight_hashes),
        'reference_restore_note':'TF2.4 reports non-variable object graph reference warnings; strict variable restore and all ordered variable hashes are checked against TF2.15',
        'max_absolute_error':float(error.max()),'mean_absolute_error':float(error.mean()),
        'reference_max_absolute_value':float(np.abs(results).max()),'samples':len(results),
        'rtol':1e-4,'atol':1e-4,'all_absolute_score_mode_orders_equal':order_equal,
        'scope':'CPU TF2.4 original vs CPU TF2.15 compatibility patch, complete official checkpoint restore'}
    (report_directory/'tf24_tf215_parity.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    assert passed,'Framework parity tolerance exceeded'

if __name__=='__main__':main()
