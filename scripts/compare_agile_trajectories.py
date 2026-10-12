"""Compare complete postprocessed ROS2 references, not only raw neural outputs."""
from pathlib import Path
import json
import numpy as np
ROOT=Path('/workspace');folder=ROOT/'artifacts/environment'
reference=np.load(folder/'agile_tensorflow_cpu_ros2_trajectories.npy')
converted=np.load(folder/'agile_torch_cpu_ros2_trajectories.npy')
assert reference.shape==converted.shape==(5,10,14)
np.testing.assert_array_equal(reference[:,:,0],converted[:,:,0])
errors={name:float(np.abs(reference[:,:,slice_]-converted[:,:,slice_]).max()) for name,slice_ in
        [('position_m',slice(1,4)),('velocity_mps',slice(4,7)),('acceleration_mps2',slice(7,10))]}
dot=np.abs(np.sum(reference[:,:,10:14]*converted[:,:,10:14],axis=-1))
errors['orientation_rad']=float((2*np.arccos(np.clip(dot,0,1))).max())
tolerances={'position_m':1e-4,'velocity_mps':1e-3,'acceleration_mps2':1e-2,'orientation_rad':1e-3}
passed=all(errors[k]<=v for k,v in tolerances.items())
report={'status':'passed' if passed else 'failed','cases':5,'points_per_case':10,'max_errors':errors,'tolerances':tolerances,
        'scope':'TF2.15 official checkpoint vs convertedPyTorch, entire originalC++ fitting/arc-length and ROS2 output on identical recorded inputs; CPU only'}
(folder/'agile_complete_reference_parity.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report));assert passed,'Complete Agile reference conversion differs beyond tolerance'
