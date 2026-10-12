from pathlib import Path
import json
import numpy as np
import pytest
from yopo_eval.task_spec import resolve_episode,verify_runtime_admission

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'benchmarks/protocol_v1/protocol.json'


def test_all_conditions_share_paired_tasks_and_independent_maps():
    p=json.loads(PROTOCOL.read_text());assert len(p['episodes'])==1800
    assert len({v['id'] for v in p['episodes']})==1800
    for name in ['yopo_seed0','yopo_seed1','yopo_seed2','topotraj','agile_autonomy','mppi_reference17']:
        rows=[v for v in p['episodes'] if v['model']==name];assert len(rows)==300
        for density in ['sparse','dense']:
            for speed in [2,4,6,8,10]:
                subset=[v for v in rows if p['tasks'][v['task_index']]['condition']==density and v['speed_mps']==speed]
                assert len(subset)==30 and sum(v['paper_first10'] for v in subset)==10
                assert len({p['tasks'][v['task_index']]['map_seed'] for v in subset if v['paper_first10']})==10
    for row in p['episodes'][::75]:
        mission=resolve_episode(PROTOCOL,row['id'])
        np.testing.assert_allclose(np.linalg.norm(np.array(mission['task']['goal'])-mission['task']['start']),50.)


def test_unknown_baseline_never_silently_falls_back():
    with pytest.raises(ValueError):resolve_episode(PROTOCOL,'missing_method_sparse_v2_trial00')
    mission=resolve_episode(PROTOCOL,'mppi_reference17_sparse_v2_trial00')
    assert mission['backend']=='mppi_reference17' and mission['training_seed'] is None


def test_development_state_is_not_admitted_as_formal_benchmark():
    mission=resolve_episode(PROTOCOL,'yopo_seed0_sparse_v2_trial00')
    if not (PROTOCOL.parent/'runtime_validation.json').is_file():
        with pytest.raises(ValueError,match='not been validated'):
            verify_runtime_admission(ROOT,PROTOCOL,mission)
