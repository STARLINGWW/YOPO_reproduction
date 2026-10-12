"""Extract exact upstream numerical method bodies; no ROS1 runtime dependency."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'external/agile_autonomy/data_generation/agile_autonomy_utils/src/trajectory_ext.cpp'
text=source.read_text(encoding='utf-8')
signatures=['void TrajectoryExt::fitPolynomialCoeffs(',
            'void TrajectoryExt::resamplePointsFromPolyCoeffs()',
            'Eigen::Vector3d TrajectoryExt::evaluatePoly(',
            'bool TrajectoryExt::setConstantArcLengthSpeed(']
functions=[];entries=[]
for signature in signatures:
    start=text.index(signature);opening=text.index('{',start);depth=1;end=opening+1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}');end+=1
    body=text[start:end];functions.append(body)
    entries.append({'signature':signature,'line':text[:start].count('\n')+1,
                    'sha256':hashlib.sha256(body.encode()).hexdigest()})
folder=ROOT/'ros2_ws/src/yopo_agile_core';(folder/'src').mkdir(parents=True,exist_ok=True)
(folder/'src/upstream_methods.inc').write_text('// Exact numerical functions from pinned Agile Autonomy; see provenance.json\n\n'+'\n\n'.join(functions)+'\n',encoding='utf-8')
(folder/'provenance.json').write_text(json.dumps({'commit':'958c0d22e11d28a4d73b627029cf62ef1a1a95ab',
    'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'functions':entries,'changes':'None inside extracted method bodies',
    'boundary_note':'Caller initializes every state derivative; fixes upstream undefined initial jerk when no previous reference. Preserve constructor time rebase (0.1..1.0 minus0.1), replaceFirstPoint (10 points), and original arc-length sampler quirks.'},indent=2)+'\n',encoding='utf-8')
(folder/'LICENSE').write_bytes((ROOT/'external/agile_autonomy/LICENSE').read_bytes())
