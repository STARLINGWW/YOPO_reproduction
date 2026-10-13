"""Read-only model/data probe for explaining note-to-implementation alignment.

CPU only; no optimizer step, no flight, no modification to training artifacts.
This is a graph inspection, not a new training run or performance benchmark.
"""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import torch
from yopo_repro.policy import build_policy, prepare_observation, decode_all, MapBank, GuidanceCost
from yopo_repro.dataset import ForestDataset, stack_batch

torch.set_num_threads(4)
policy, profile, cfg = build_policy('cpu')
checkpoint = ROOT / 'checkpoints/formal_main_v1_seed0/best_policy.pth'
before = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
policy.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
policy.eval()
dataset = ForestDataset(ROOT / 'datasets/isaac_full_v1', 'test', cfg, seed=0)
bank = MapBank(ROOT / 'datasets/isaac_full_v1', dataset.shards, cfg)
depth, pos, rotation, obs, map_id = stack_batch(dataset, [0, 1])
shapes = {'depth': list(depth.shape), 'observation': list(obs.shape)}
def backbone_hook(module, inputs, output):
    shapes['visual_features'] = list(output.shape)
def head_hook(module, inputs, output):
    shapes['head_input'] = list(inputs[0].shape)
    shapes['head_raw_output'] = list(output.shape)
handles = [policy.image_backbone.register_forward_hook(backbone_hook), policy.yopo_header.register_forward_hook(head_hook)]
prepared = torch.from_numpy(prepare_observation(obs, policy))
shapes['primitive_frame_state'] = list(prepared.shape)
prediction = policy(torch.from_numpy(depth), prepared)
for h in handles: h.remove()
ends = decode_all(policy, prediction)
cost = GuidanceCost.apply(ends, pos, rotation, obs, map_id, bank)
score = prediction[:, 9].reshape(len(depth), 15)
trajectory = cost.mean()
score_loss = torch.nn.functional.smooth_l1_loss(score, cost.detach())
total = profile['trajectory_loss_weight'] * trajectory + profile['score_loss_weight'] * score_loss
shapes.update(prediction=list(prediction.shape), decoded_endstates=list(ends.shape), true_cost=list(cost.shape), predicted_cost=list(score.shape))

score_to_ends = torch.autograd.grad(score_loss, ends, allow_unused=True, retain_graph=True)[0]
traj_to_score = torch.autograd.grad(trajectory, score, allow_unused=True, retain_graph=True)[0]
mean_gradient = torch.autograd.grad(trajectory, cost, retain_graph=True)[0]
score_gradient = torch.autograd.grad(score_loss, score, retain_graph=True)[0]
expected_score_gradient = torch.clamp(score.detach().double() - cost.detach(), -1, 1) / cost.numel()
shared = policy.image_backbone.cnn.conv1.weight
g_traj = torch.autograd.grad(trajectory, shared, retain_graph=True)[0]
g_score = torch.autograd.grad(score_loss, shared, retain_graph=True)[0]
g_total = torch.autograd.grad(total, shared)[0]
gradient_sum_error = float((g_total - (profile['trajectory_loss_weight']*g_traj + profile['score_loss_weight']*g_score)).abs().max())

audit = json.loads((checkpoint.parent/'training_audit.json').read_text(encoding='utf-8'))
code_files = list((ROOT/'src/yopo_repro').glob('*.py')) + [ROOT/'scripts/train_scratch.py', ROOT/'configs/paper_aligned.json']
code_files += [ROOT/'external/audit_sources/main/flightpolicy/yopo'/n for n in ['yopo_policy.py','yopo_network.py','resnet.py','primitive_utils.py']]
digest = hashlib.sha256()
for path in sorted(code_files):
    digest.update(path.relative_to(ROOT).as_posix().encode()); digest.update(path.read_bytes())
manifest = json.loads((checkpoint.parent/'run_manifest.json').read_text(encoding='utf-8'))
notes = Path(r'<旧机器>/paper_reading/YOPO\sources\conversation.txt')
result = {
    'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
    'scope': 'two offline test samples, audited seed0, CPU graph inspection only; eval mode, no optimizer step, no simulator',
    'environment': {'torch':torch.__version__, 'numpy':np.__version__, 'device':'cpu', 'historical_training_torch':manifest['torch'], 'limitation':'Host libraries differ from the formal training container; this probe confirms graph structure, not historical numerical replay or model quality.'},
    'note_source': str(notes), 'note_sha256': hashlib.sha256(notes.read_bytes()).hexdigest(),
    'checkpoint_sha256': before,
    'checkpoint_matches_training_audit': before == audit['selection']['best_policy_file_sha256'],
    'checkpoint_file_unchanged': before == hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    'training_code_sha256':digest.hexdigest(), 'training_code_matches_manifest':digest.hexdigest()==manifest['code_sha256'],
    'sample_indices':[0,1], 'shapes':shapes,
    'losses':{'trajectory':float(trajectory.detach()), 'score':float(score_loss.detach()), 'total':float(total.detach()), 'weights':[profile['trajectory_loss_weight'],profile['score_loss_weight']]},
    'gradient_checks': {
        'score_loss_has_no_direct_path_to_decoded_endstates':score_to_ends is None,
        'trajectory_loss_has_no_direct_path_to_score_tensor':traj_to_score is None,
        'mean_cost_gradient_expected':1/cost.numel(),
        'mean_cost_gradient_min':float(mean_gradient.min()), 'mean_cost_gradient_max':float(mean_gradient.max()),
        'score_smooth_l1_mean_gradient_max_abs_error':float((score_gradient.double()-expected_score_gradient).abs().max()),
        'shared_backbone_trajectory_gradient_norm':float(g_traj.norm()),
        'shared_backbone_score_gradient_norm':float(g_score.norm()),
        'weighted_gradient_sum_max_abs_error':gradient_sum_error,
        'weighted_gradient_sum_allclose':bool(torch.allclose(g_total,g_traj+10*g_score,rtol=1e-5,atol=1e-7))},
    'predicted_costs':score.detach().tolist(), 'map_evaluated_costs':cost.detach().tolist(),
    'selected_by_predicted_cost':score.detach().argmin(dim=1).tolist(),
    'oracle_best_by_map_cost':cost.detach().argmin(dim=1).tolist(),
    'selection_note':'Indices refer to flattened network output slots, zero-based; physical lattice index is 14-slot.'
}
output = Path(__file__).with_name('training_graph_trace.json')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['predicted_costs','map_evaluated_costs']},ensure_ascii=False,indent=2))
