"""Actual scratch checkpoint inference and standard ROS2 trajectory boundary check.

CPU is used so this can run during serial GPU data collection. This is not a
closed-loop success-rate test and does not satisfy the final navigation gate.
"""
from pathlib import Path
import json
import numpy as np
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from yopo_runtime.main_planner import MainPlanner
from yopo_runtime.frame_gate import Observation

ROOT=Path('/workspace')
shard=ROOT/'datasets/smoke_v1/shards/002'
depth=np.load(shard/'depth_m.npy',mmap_mode='r');labels=np.load(shard/'poses.npz')
planner=MainPlanner(ROOT/'checkpoints/resume_split_v2/best_policy.pth',speed=2.,device='cpu')
results=[]
for i in range(5):
    planner.reset(i)
    image=Image();image.header.frame_id=f'e{i}/camera_optical';image.header.stamp.sec=1
    image.width=160;image.height=90;image.step=640;image.encoding='32FC1';image.data=depth[i].tobytes()
    odom=Odometry();odom.header.frame_id=f'e{i}/world';odom.header.stamp=image.header.stamp;odom.child_frame_id=f'e{i}/base_link'
    p=labels['positions'][i];q=labels['quaternions'][i]
    odom.pose.pose.position.x,odom.pose.pose.position.y,odom.pose.pose.position.z=map(float,p)
    odom.pose.pose.orientation.w,odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z=map(float,q)
    from scipy.spatial.transform import Rotation
    goal_pos=p+Rotation.from_quat(q[[1,2,3,0]]).apply([10.,0.,0.])
    goal=PoseStamped();goal.header.frame_id=f'e{i}/world'
    goal.pose.position.x,goal.pose.position.y,goal.pose.position.z=map(float,goal_pos)
    trajectory=planner(Observation(i,1,1_000_000_000,image,odom),goal)
    assert len(trajectory.points)==21 and trajectory.header.frame_id==f'e{i}/world'
    first=trajectory.points[0].transforms[0].translation
    np.testing.assert_allclose([first.x,first.y,first.z],p,atol=1e-10)
    for point in trajectory.points:
        pos=point.transforms[0].translation;assert np.isfinite([pos.x,pos.y,pos.z]).all()
    results.append(planner.last_debug)
report={'status':'passed','scope':'scratch smoke checkpoint, 5 independent depth/pose samples -> standard ROS2 trajectories on CPU; not dynamic flight',
        'checkpoint':'checkpoints/resume_split_v2/best_policy.pth','official_weights_loaded':False,'samples':results}
(ROOT/'artifacts/environment/trained_planner_interface.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
