"""Translate static parameters from pinned upstream XML; explicit test overrides."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
xml = ROOT / 'external/Fast-Planner/fast_planner/plan_manage/launch/topo_algorithm.xml'
params = {}
for element in ET.parse(xml).iter('param'):
    name, value = element.get('name'), element.get('value', '')
    if not name.startswith(('sdf_map/', 'topo_prm/', 'optimization/', 'manager/', 'fsm/')) or '$(' in value:
        continue
    if value in ('true', 'false'):
        value = value == 'true'
    else:
        try:
            value = float(value) if '.' in value or element.get('type') == 'double' else int(value)
        except ValueError:
            pass
    params[name.replace('/', '.')] = value
overrides = {
    'sdf_map.map_size_x': 20.0, 'sdf_map.map_size_y': 20.0, 'sdf_map.map_size_z': 6.0,
    'sdf_map.fx': 80.0, 'sdf_map.fy': 80.0, 'sdf_map.cx': 80.0, 'sdf_map.cy': 45.0,
    'sdf_map.local_map_margin': 10, 'sdf_map.virtual_ceil_height': -1.0,
    'sdf_map.visualization_truncate_height': 5.0,
    'optimization.max_vel': 4.0, 'optimization.max_acc': 6.0,
    'manager.max_vel': 4.0, 'manager.max_acc': 6.0,
    'fsm.flight_type': 1, 'fsm.waypoint_num': 0,
    'topo_prm.seed': 42,
    # Deterministic component regression uses generous wall-clock caps.
    'topo_prm.max_sample_time': 2.0, 'topo_prm.parallel_shortcut': False,
    'optimization.max_iteration_time1': 1.0, 'optimization.max_iteration_time2': 1.0,
}
params.update(overrides)
folder = ROOT / 'configs/topotraj'
folder.mkdir(parents=True, exist_ok=True)
lines = ['/**:', '  ros__parameters:']
for name, value in params.items():
    lines.append(f'    {name}: {json.dumps(value)}')
(folder / 'component_test.yaml').write_text('\n'.join(lines) + '\n', encoding='utf-8')
(folder / 'component_test_provenance.json').write_text(json.dumps({
    'scope': 'Component regression ONLY, not timed benchmark configuration',
    'source': str(xml.relative_to(ROOT)), 'explicit_overrides': overrides,
}, indent=2) + '\n', encoding='utf-8')

# Native integration candidate. Preserve published algorithm/time budgets;
# these defaults are NOT promoted to the final tuned benchmark configuration.
candidate=dict(params)
candidate.update({'sdf_map.map_size_x':80.,'sdf_map.map_size_y':80.,'sdf_map.map_size_z':8.,
    'sdf_map.ground_height':0.,'sdf_map.cx':79.5,'sdf_map.cy':44.5,
    'sdf_map.local_map_margin':50,'sdf_map.visualization_truncate_height':8.,
    'topo_prm.max_sample_time':.005,'topo_prm.parallel_shortcut':True,
    'optimization.max_iteration_time1':.0001,'optimization.max_iteration_time2':.005})
lines=['/**:','  ros__parameters:']+[f'    {name}: {json.dumps(value)}' for name,value in candidate.items()]
(folder/'isaac_development.yaml').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(folder/'isaac_development_provenance.json').write_text(json.dumps({'status':'candidate_not_final_benchmark',
    'source':str(xml.relative_to(ROOT)),'geometry_adapter':'80x80x8m, calibrated160x90 camera with pixel-index principal point79.5/44.5',
    'effective_mapping_depth_range_m':4.5,'raw_common_optical_depth_range_m':20.,
    'pending':'Validate/tune mapping range and compute tradeoff on development maps; do not silently use this candidate for final comparison'},indent=2)+'\n')
