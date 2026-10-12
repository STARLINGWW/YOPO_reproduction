"""The DAgger collection driver must be plannable without touching the GPU."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import run_dagger_collection as driver


def test_plan_only_records_usable_and_skipped_seeds(tmp_path,monkeypatch,capsys):
    checkpoint = tmp_path/'best_policy.pth'
    checkpoint.write_bytes(b'unit-test-checkpoint')
    run_dir = tmp_path/'flights'
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.setattr(driver,'require_training_gpu_released',lambda:raise_assert())
    monkeypatch.setattr(sys,'argv',['run_dagger_collection.py','--run','plan_check',
                                    '--checkpoint','unit/best_policy.pth','--map-seeds','7000,7001',
                                    '--flights-per-map','2','--plan-only'])
    (tmp_path/'checkpoints'/'unit').mkdir(parents=True)
    (tmp_path/'checkpoints'/'unit'/'best_policy.pth').write_bytes(b'unit-test-checkpoint')
    driver.main()
    plan = json.loads((tmp_path/'artifacts/dagger_flights/plan_check_plan.json').read_text(encoding='utf-8'))
    assert plan['status']=='plan_only'
    assert [f['map_seed'] for f in plan['flights']]==[7000,7000]
    assert [f['speed_mps'] for f in plan['flights']]==[1.5,2.5]
    assert [f['duration_s'] for f in plan['flights']]==[20,30]
    assert plan['flights'][0]['endpoint_clearance_m']>=1.0
    assert any(item['map_seed']==7001 for item in plan['skipped'])


def raise_assert():
    raise AssertionError('plan-only must not require the GPU guard')
