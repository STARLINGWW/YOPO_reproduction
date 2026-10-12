"""Build reference from original SO3Control; only remove its unused ROS1 include."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'external/Fast-Planner/uav_simulator/so3_control'
dest=ROOT/'ros2_ws/src/yopo_quad_reference/vendor';(dest/'so3_control').mkdir(parents=True,exist_ok=True)
records=[]
for source,target in [(base/'src/SO3Control.cpp',dest/'SO3Control.cpp'),
                      (base/'include/so3_control/SO3Control.h',dest/'so3_control/SO3Control.h')]:
    text=source.read_text(encoding='utf-8').replace('#include <ros/ros.h>','// Unused ROS1 include removed for standalone numerical reference.')
    target.write_text(text,encoding='utf-8')
    records.append({'source':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
(dest.parent/'LICENSE').write_bytes((ROOT/'external/Fast-Planner/LICENSE').read_bytes())
(dest.parent/'provenance.json').write_text(json.dumps({'commit':'41be219fe4ecc43bf0e0c2b42a523f8755ccc0bd','files':records,
    'change':'Unused ros/ros.h include only; original numerical control implementation unchanged'},indent=2)+'\n')
