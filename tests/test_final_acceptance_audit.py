"""The final acceptance audit must be able to report 'verified' when every
piece of evidence exists, and must keep reporting gaps when anything is
missing. A false 'pending' at the very end would hide finished work, and a
false 'verified' would be worse, so both directions are checked here against a
synthetic complete tree (no GPU, no Isaac)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import final_acceptance_audit as audit


def write(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload),encoding='utf-8')


def complete_tree(root,prefix='formal_main_v1'):
    for seed in (0,1,2):
        folder = root/'checkpoints'/('%s_seed%d'%(prefix,seed))
        write(folder/'training_audit.json',{'status':'passed','epochs':50,'seed':seed,
            'selection':{'best_epoch':40,'best_policy_file_sha256':'%064d'%seed,
                         'initial_model_tensor_sha256':'%064d'%(seed+10)}})
        write(folder/'result.json',{'status':'complete','epochs':50,'steps':312500})
    for seed in (0,1,2):
        write(root/'artifacts/expert'/('network_comparison_trained_seed%d.json'%seed),
              {'status':'complete','samples':10000,'sample_alignment_max_abs_error':0.0,
               'checkpoint':{'kind':'trained_seed%d'%seed,'sha256':'%064d'%seed},
               'network_vs_expert':{'scaled_gd50':{}}})
    write(root/'artifacts/expert/network_comparison_random_initial.json',
          {'status':'complete','samples':10000,'sample_alignment_max_abs_error':0.0,
           'checkpoint':{'kind':'random_initial'},'network_vs_expert':{'scaled_gd50':{}}})
    write(root/'benchmarks/protocol_v1/runtime_validation.json',
          {'status':'passed','protocol_sha256':'x','validated_backends':['yopo','agile','topotraj'],
           'runtime_files':{'a':'b'},'consumed_episode_ids':[]})
    write(root/'artifacts/agile_autonomy/torch_export_v1/torch_cuda_parity.json',{'status':'passed'})
    scope = load_scope()
    write(root/'benchmarks/protocol_v1/active_scope_yopo_only.json',scope)
    write(root/'datasets/isaac_dagger_v1/aggregation_manifest.json',{'status':'complete'})
    write(root/'checkpoints/dagger_main_v1_seed0/result.json',{'status':'complete','scope':'dagger_aggregation_finetune_not_formal_seed'})
    write(root/'artifacts/benchmark_summary/summary.json',{'status':'outcome_coverage_complete',
          'completed_episodes':1500,'expected_episodes':1500,'invalid_evidence':[],'duplicate_primary_attempts':[],
          'active_scope':{'models':scope['active_models']}})
    write(root/'artifacts/benchmark_summary/matrix_result.json',{'status':'batch_finished','failures':[]})
    write(root/'artifacts/benchmark_summary/plan.json',{'pending_episodes':0})
    showcase = root/'artifacts/ros2_showcase/showcase_final'
    video = showcase/'global_trajectory.mp4';video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(b'video')
    write(showcase/'render_manifest.json',{'navigation_status':'success',
          'checkpoint_sha256':'%064d'%0,'video':video.relative_to(root).as_posix()})
    write(root/'artifacts/environment/command_evidence_audit.json',{'status':'passed'})


def load_scope():
    return {'id':'yopo_only_1500',
            'active_models':['yopo_seed0','yopo_seed1','yopo_seed2','topotraj','agile_autonomy'],
            'per_model_episodes':300,'expected_episodes':1500}


def run_audit(root,monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'argv',['final_acceptance_audit.py','--root',str(root),
                                    '--output',str(tmp_path/'audit.json')])
    audit.main()
    return json.loads((tmp_path/'audit.json').read_text(encoding='utf-8'))


def test_audit_flips_to_verified_when_the_whole_chain_is_present(tmp_path,monkeypatch):
    root = tmp_path/'project';complete_tree(root)
    report = run_audit(root,monkeypatch,tmp_path)
    statuses = {item['id']:item['status'] for item in report['items']}
    assert statuses['three_seed_training']=='verified'
    assert statuses['expert_50_step_comparison']=='verified'
    assert statuses['baseline_native_validation']=='verified'
    assert statuses['dagger_finetune']=='verified'
    assert statuses['benchmark_matrix']=='verified'
    assert statuses['final_showcase_and_audit']=='verified'
    assert 'mppi_reference17' not in statuses
    assert report['counts']=={'verified':6}
    assert report['all_verified'] is True


def test_audit_keeps_reporting_gaps(tmp_path,monkeypatch):
    root = tmp_path/'project';complete_tree(root)
    # remove one training audit, one expert comparison and the showcase manifest
    (root/'checkpoints/formal_main_v1_seed1/training_audit.json').unlink()
    (root/'artifacts/expert/network_comparison_trained_seed2.json').unlink()
    (root/'artifacts/ros2_showcase/showcase_final/render_manifest.json').unlink()
    report = run_audit(root,monkeypatch,tmp_path)
    statuses = {item['id']:item['status'] for item in report['items']}
    assert statuses['three_seed_training']=='pending'
    assert statuses['expert_50_step_comparison']=='pending'
    assert statuses['final_showcase_and_audit']=='pending'
    assert report['all_verified'] is False
    assert statuses['benchmark_matrix']=='verified'  # untouched evidence stays verified


def test_matrix_item_requires_a_clean_aggregate_not_only_coverage(tmp_path,monkeypatch):
    root = tmp_path/'project';complete_tree(root)
    scope = load_scope()
    write(root/'artifacts/benchmark_summary/summary.json',{'status':'invalid_evidence',
          'completed_episodes':1500,'expected_episodes':1500,
          'active_scope':{'models':scope['active_models']},
          'invalid_evidence':[{'run':'some_run','episode_id':'some_episode','error':'validation missing'}],
          'duplicate_primary_attempts':[]})
    report = run_audit(root,monkeypatch,tmp_path)
    items = {item['id']:item for item in report['items']}
    assert items['benchmark_matrix']['status']=='pending'
    assert 'invalid_evidence=1' in items['benchmark_matrix']['detail']
    assert 'aggregate_status=invalid_evidence' in items['benchmark_matrix']['detail']


def test_out_of_scope_skips_do_not_block_the_active_matrix(tmp_path,monkeypatch):
    root = tmp_path/'project';complete_tree(root)
    write(root/'artifacts/benchmark_summary/matrix_result.json',{'status':'batch_finished',
          'failures':[{'episode_id':'mppi_reference17_sparse_v2_trial00',
                       'problem':'mppi_reference17 has no validated native adapter; not substituted'}]})
    report = run_audit(root,monkeypatch,tmp_path)
    items = {item['id']:item for item in report['items']}
    assert items['benchmark_matrix']['status']=='verified'
