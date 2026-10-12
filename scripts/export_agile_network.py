"""Export all official Keras tensors/configs without retraining or approximation."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,hashlib,json
import numpy as np
import cv2
import tensorflow as tf
from scipy.spatial.transform import Rotation
ROOT=Path('/workspace');output=ROOT/'artifacts/agile_autonomy/torch_export_v1'


def main():
    tf.config.set_visible_devices([], 'GPU');output.mkdir(exist_ok=True)
    if any(output.iterdir()):raise FileExistsError('Do not overwrite an existing export')
    spec=importlib.util.spec_from_file_location('agile_nets_export',ROOT/'vendor/agile_ros2/nets.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=SimpleNamespace(img_height=224,img_width=224,use_rgb=False,use_depth=True,freeze_backbone=False,
        modes=3,predict_state_number=[],out_seq_len=10,state_dim=3,seq_len=1,use_position=False,use_attitude=True)
    model=module.create_network(config)
    model({'depth':np.zeros((1,1,224,224,3),np.float32),'imu':np.zeros((1,1,21),np.float32)},training=False)
    source=ROOT/'external/agile_autonomy/planner_learning/models/ckpt-50'
    restore=tf.train.Checkpoint(net=model).restore(str(source));restore.assert_existing_objects_matched();restore.expect_partial()
    reference=json.loads((ROOT/'artifacts/agile_autonomy/tf215_probe.json').read_text())
    assert [hashlib.sha256(w.numpy().tobytes()).hexdigest() for w in model.weights]==reference['ordered_weight_sha256']
    groups={};arrays={};hashes=[];named_variables={}
    for group in ['backbone','resize_op','img_mergenet','resize_op_2','states_conv','resize_op_3','plan_module']:
        layers=model.backbone[0].layers if group=='backbone' else getattr(model,group)
        records=[]
        for i,layer in enumerate(layers):
            keys=[]
            for j,value in enumerate(layer.get_weights()):
                key=f'{group}_{i}_{j}';arrays[key]=value;keys.append(key)
                hashes.append(hashlib.sha256(value.tobytes()).hexdigest())
                variable_name=layer.weights[j].name
                assert variable_name not in named_variables,'Duplicate Keras variable name'
                named_variables[variable_name]={'array_key':key,'sha256':hashes[-1],'shape':list(value.shape)}
            records.append({'class':layer.__class__.__name__,'config':layer.get_config(),'weights':keys})
        groups[group]=records
    original_named={w.name:hashlib.sha256(w.numpy().tobytes()).hexdigest() for w in model.weights}
    assert {k:v['sha256'] for k,v in named_variables.items()}==original_named,'Export dropped or changed a named network variable'
    np.savez(output/'weights.npz',**arrays)
    original=np.load(ROOT/'artifacts/agile_autonomy/tf215_parity_inputs_outputs.npz')
    depths=list(original['depth']);imus=list(original['imu']);kinds=['synthetic_random']*len(depths)
    for pattern in [np.zeros((224,224)),np.full((224,224),250.),np.tile(np.linspace(0,250,224),(224,1)),
                    np.indices((224,224)).sum(axis=0)%2*250.]:
        depths.append(np.repeat(pattern[...,None],3,axis=-1)[None].astype(np.float32))
        imu=np.zeros((1,21),np.float32);imu[:,3:12]=np.eye(3).reshape(1,9);imu[:,-3]=1.
        imus.append(imu);kinds.append('structured_depth')
    flight=np.load(ROOT/'artifacts/ros2_flights/ros2_scratch_checkpoint_20260924_061715/flight.npz')
    for i in np.linspace(0,len(flight['frames'])-1,16).astype(int):
        row=flight['frames'][i];p=row[1:4];rotation=Rotation.from_quat(row[4:8][[1,2,3,0]]).as_matrix()
        goal=flight['goal']-p;goal/=max(np.linalg.norm(goal),1e-9)
        depth=cv2.resize(flight['depths'][i]*12.5,(224,224),interpolation=cv2.INTER_LINEAR)
        depths.append(np.repeat(depth[...,None],3,axis=-1)[None].astype(np.float32))
        imus.append(np.r_[p,rotation.reshape(-1),rotation.T@row[8:11],np.zeros(3),rotation.T@goal][None].astype(np.float32))
        kinds.append('recorded_development_flight_pose_depth_velocity_zero_gyro_fixture')
    depths=np.stack(depths);imus=np.stack(imus)
    outputs=np.concatenate([model({'depth':depths[i:i+1],'imu':imus[i:i+1]},training=False).numpy() for i in range(len(imus))])
    np.savez(output/'parity_inputs_outputs.npz',depth=depths,imu=imus,outputs=outputs)
    metadata={'schema':1,'classification':'Official Agile Autonomy inference conversion, no training',
        'source_checkpoint_sha256':hashlib.sha256(json.dumps(reference['checkpoint_files'],sort_keys=True).encode()).hexdigest(),
        'upstream_commit':'958c0d22e11d28a4d73b627029cf62ef1a1a95ab','config':vars(config),'groups':groups,
        'variable_count':len(hashes),'ordered_weight_sha256':hashes,'weights_file_sha256':hashlib.sha256((output/'weights.npz').read_bytes()).hexdigest(),
        'named_variables':named_variables,'keras_model_order_weight_sha256':reference['ordered_weight_sha256'],
        'parity_sample_kinds':kinds,'source_tensorflow':tf.__version__}
    (output/'manifest.json').write_text(json.dumps(metadata,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')
    print(json.dumps({'status':'exported','variables':len(hashes),'cases':len(imus),'layer_classes':sorted(set(v['class'] for g in groups.values() for v in g))}))


if __name__=='__main__':main()
