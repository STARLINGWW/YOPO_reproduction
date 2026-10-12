"""Run the original C++ VoxelGrid and compare cell queries, including boundaries."""
from pathlib import Path
import json
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
from yopo_repro.maps import VoxelSDF

rng=np.random.default_rng(17)
queries=rng.uniform([-1.3,-2.3,-3.3],[.6,0.,-.8],(200,3))
queries=np.vstack([queries,[-1.01,-2,-3],[-1.21,-2,-3],[-1,-2,-3],[.4,-.4,-1.2]])
coords=np.indices((7,8,9))
field=(np.sin(.3*coords[0])+.1*coords[1]**2-.2*coords[2]).astype(np.float32)
values,_,valid=VoxelSDF(field,[-1,-2,-3],.2).query(queries)
payload="\n".join(" ".join(format(v,".17g") for v in p) for p in queries)+"\n"
reference=json.loads(subprocess.check_output(["ros2","run","yopo_math_reference","voxel_reference"],input=payload,text=True))
assert len(reference)==len(queries)
for i,result in enumerate(reference):
    assert bool(valid[i])==result['valid'],(queries[i],valid[i],result)
    if result['valid']:
        np.testing.assert_allclose(values[i],result['value'],atol=2e-7,rtol=0)
report={"status":"passed","queries":len(queries),"scope":"original C++ VoxelGrid indexing and stored-cell values; not whole sdf_tools construction"}
(ROOT/"artifacts/environment/voxel_cpp_parity.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
