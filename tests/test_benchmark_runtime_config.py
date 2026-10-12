"""The frozen runtime declaration must stay consistent with its sources."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'configs/benchmark_runtime/v1.json'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def test_runtime_files_exist():
    config = load(CONFIG)
    missing = [name for name in config['runtime_files']['list'] if not (ROOT/name).is_file()]
    assert missing==[]
    assert len(config['runtime_files']['list'])>=20
    for required in ('scripts/evaluate_ros2_flight.py','scripts/run_benchmark_matrix.py','scripts/validate_ros2_flight.py'):
        assert required in config['runtime_files']['list']


def test_criteria_are_verbatim_protocol_criteria():
    config = load(CONFIG);protocol = load(ROOT/'benchmarks/protocol_v1/protocol.json')
    for key,value in protocol['criteria'].items():
        assert config['common']['task_definition']['criteria'][key]==value, key


def test_vehicle_and_sensor_match_their_sources():
    config = load(CONFIG);vehicle = load(ROOT/'configs/unified_quad.json')
    common = config['common']
    assert common['vehicle']['collision_envelope_radius_m']==vehicle['collision_envelope_radius_m']
    assert common['vehicle']['physics_dt_s']==vehicle['physics_dt_s']
    assert common['vehicle']['control_dt_s']==vehicle['control_dt_s']
    assert common['vehicle']['mass_kg']==vehicle['mass_kg']
    sensor = common['sensor']
    assert (sensor['width'],sensor['height'])==(160,90)
    assert sensor['max_depth_m']==20.0
    runner = (ROOT/'scripts/run_ros2_navigation.py').read_text(encoding='utf-8')
    assert "'cx_pixel_index':79.5" in runner.replace(' ','')
    assert "info.k=[80.,0.,79.5,0.,80.,44.5,0.,0.,1.]" in runner


def test_timeout_rule_reproduces_every_episode():
    protocol = load(ROOT/'benchmarks/protocol_v1/protocol.json')
    mismatches = []
    for episode in protocol['episodes']:
        task = protocol['tasks'][episode['task_index']]
        expected = max(30.,1.5*task['straight_distance_m']/episode['speed_mps']+10.)
        if abs(expected-episode['timeout_s'])>1e-9:mismatches.append(episode['id'])
    assert mismatches==[]


def test_every_matrix_model_has_a_declared_method():
    config = load(CONFIG);protocol = load(ROOT/'benchmarks/protocol_v1/protocol.json')
    models = {episode['model'] for episode in protocol['episodes']}
    assert models<=set(config['methods'])
    assert config['methods']['expert_50_steps']['in_1800_matrix'] is False
    assert config['methods']['mppi_reference17']['slots']==300
    assert config['methods']['mppi_reference17']['status']=='documented_gap_no_official_implementation'
    for seed in (0,1,2):
        entry = config['methods']['yopo_seed%d'%seed]
        assert entry['training_seed']==seed and entry['device']=='cuda'
        assert entry['weights'].endswith('formal_main_v1_seed%d/best_policy.pth'%seed)


def test_declared_differences_and_prohibitions_are_present():
    config = load(CONFIG)
    topotraj = config['methods']['topotraj']['declared_differences']
    assert any('4.5' in item for item in topotraj)
    assert any('6.0' in item for item in topotraj)
    joined = ' '.join(config['prohibitions'])
    assert 'MPPI' in joined and 'official YOPO weights' in joined
    assert config['status']=='declared_pending_native_admission'
