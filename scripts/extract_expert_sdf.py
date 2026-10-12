"""Extract original sdf_tools finite-difference method, retain original VoxelGrid."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'external/audit_sources/main/flightlib/third_party/sdf_tools/src/sdf_tools/sdf.cpp'
text=source.read_text(encoding='utf-8')
signature='std::vector<double> SignedDistanceField::GetGradient(const int64_t x_index'
start=text.index(signature);opening=text.index('{',start);end=opening+1;depth=1
while depth:
    depth+=(text[end]=='{')-(text[end]=='}');end+=1
function=text[start:end]
folder=ROOT/'ros2_ws/src/yopo_expert_core';(folder/'src').mkdir(parents=True,exist_ok=True)
(folder/'src/original_gradient.inc').write_text(function+'\n',encoding='utf-8')
files=[source,ROOT/'external/audit_sources/main/flightlib/src/grad_traj_optimization/grad_traj_optimizer.cpp',
       ROOT/'external/audit_sources/main/flightlib/src/grad_traj_optimization/qp_generator.cpp',
       ROOT/'external/audit_sources/main/flightlib/third_party/arc_utilities/include/arc_utilities/voxel_grid.hpp']
(folder/'provenance.json').write_text(json.dumps({'classification':'Original main cost and voxel-gradient core; expert solver policy reconstructed',
    'main_commit':'881e1c549122efa5a2402b862f70a198e6e93baa',
    'reference2017_commit':'019701be8d660fc18cc482a95adeae8d9f415d82',
    'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    'gradient_function_sha256':hashlib.sha256(function.encode()).hexdigest(),
    'compatibility_fix':'Out-of-grid gradient returns a three-zero placeholder before the original boundary-distance override, avoiding original unchecked empty-vector access.',
    'solver_uncertainty':'YOPO release has no TableI expert driver. Scaled backtrackingGD50 update attempts and cited2017 NLoptMMA50 objective evaluations are separately labeled; neither is asserted to be the unpublished original solver configuration.'},indent=2)+'\n')
(folder/'LICENSE_MAIN').write_bytes((ROOT/'external/audit_sources/main/LICENSE').read_bytes())
