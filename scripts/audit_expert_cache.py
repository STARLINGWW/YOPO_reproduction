"""Independent re-computation audit of the frozen expert test cache.

Re-derives a seeded random sample of the cached test set directly from the
dataset and the pinned original-C++ expert core, then compares costs, optimized
end states and solver diagnostics against the stored arrays. This is a
verification of the cache, not a new Table-I result.
"""
from pathlib import Path
import argparse
import json
import sys
import time
import numpy as np

ROOT = Path('/workspace')
sys.path.insert(0, str(ROOT / 'src'))
from yopo_expert.core import ExpertMap, world_problem
from yopo_repro.dataset import ForestDataset, stack_batch
from yopo_repro.io import sha256_file, write_json_atomic
from yopo_repro.policy import load_config
from flightpolicy.yopo.primitive_utils import LatticeParam, LatticePrimitive

VARIANTS = ['scaled_gd50', 'mma50_evaluations']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=ROOT / 'datasets/isaac_full_v1')
    parser.add_argument('--cache', type=Path, default=ROOT / 'artifacts/expert/formal_test_v1')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20260924)
    args = parser.parse_args()

    config = json.loads((args.cache / 'config.json').read_text(encoding='utf-8'))
    result = json.loads((args.cache / 'result.json').read_text(encoding='utf-8'))

    dataset_sha = sha256_file(args.dataset / 'dataset.json')
    dataset_identity_ok = dataset_sha == config['dataset_sha256']
    file_hashes = {}
    for name, expected in result['files_sha256'].items():
        actual = sha256_file(args.cache / name)
        file_hashes[name] = {'expected': expected, 'actual': actual, 'match': actual == expected}
    hashes_ok = all(entry['match'] for entry in file_hashes.values())

    profile, cfg = load_config()
    dataset = ForestDataset(args.dataset, 'test', cfg, seed=0)
    cached = {name: np.load(args.cache / (name + '.npy'), mmap_mode='r')
              for name in ['states', 'initial_cost'] + [v + suffix for v in VARIANTS
                                                        for suffix in ['_cost', '_ends_world', '_diagnostics']]}
    if cached['states'].shape != (len(dataset), 22):
        raise ValueError('Cached state array shape is inconsistent with the dataset')
    if config['samples'] != len(dataset) or config['split'] != 'test' or config['state_seed'] != 0:
        raise ValueError('Cache config does not describe this dataset/split/seed')

    lattice = LatticePrimitive(LatticeParam(cfg))
    primitive = np.zeros((15, 3, 3))
    primitive[:, :, 0] = lattice.lattice_pos_node[::-1]
    primitive[:, :, 1] = lattice.lattice_vel_node[::-1]

    rng = np.random.default_rng(args.seed)
    indices = np.sort(rng.choice(len(dataset), size=args.samples, replace=False)).astype(int)
    errors = {'states_max_abs': 0., 'initial_cost_max_abs': 0.}
    # Diagnostics columns 0..3 (objective evaluations, accepted updates, unused,
    # non-finite evaluations) are deterministic; column 4 is C++ wall time in ms.
    per_variant = {v: {'cost_max_abs': 0., 'ends_world_max_abs': 0., 'deterministic_diagnostics_max_abs': 0.,
                       'timing_column_max_abs_ms': 0.}
                   for v in VARIANTS}
    compared = 0
    experts, started = {}, time.perf_counter()
    try:
        for index, block, in [(int(i), (int(i) // 16) * 16) for i in indices]:
            # Reconstruct exactly as the cache builder did: dense 16-sample blocks.
            block_indices = np.arange(block, min(block + 16, len(dataset)))
            _, positions, rotations, observations, ids = stack_batch(dataset, block_indices)
            local = index - block
            row = np.concatenate([positions[local], rotations[local].reshape(-1),
                                  observations[local], [ids[local]]])
            errors['states_max_abs'] = max(errors['states_max_abs'],
                                           float(np.abs(row - cached['states'][index]).max()))
            starts, initials, goals = world_problem(positions[local:local + 1], rotations[local:local + 1],
                                                    observations[local:local + 1], primitive[None], cfg['goal_length'])
            map_id = int(ids[local])
            if map_id not in experts:
                shard = next(s for s in dataset.shards if s['id'] == map_id)
                folder = args.dataset / shard['path']
                meta = json.loads((folder / 'map.json').read_text())
                if sha256_file(folder / 'sdf.npy') != meta['sdf_sha256']:
                    raise ValueError('Map field hash mismatch for map ' + str(map_id))
                experts[map_id] = ExpertMap(folder)
            expert = experts[map_id]
            base, _ = expert.evaluate(starts, initials, goals)
            errors['initial_cost_max_abs'] = max(errors['initial_cost_max_abs'],
                                                 float(np.abs(base - cached['initial_cost'][index]).max()))
            for variant in VARIANTS:
                ends, costs, diagnostics = expert.optimize(starts, initials, goals, variant)
                per_variant[variant]['cost_max_abs'] = max(
                    per_variant[variant]['cost_max_abs'],
                    float(np.abs(costs - cached[variant + '_cost'][index]).max()))
                per_variant[variant]['ends_world_max_abs'] = max(
                    per_variant[variant]['ends_world_max_abs'],
                    float(np.abs(ends.reshape(15, 3, 3) - cached[variant + '_ends_world'][index]).max()))
                stored = cached[variant + '_diagnostics'][index]
                per_variant[variant]['deterministic_diagnostics_max_abs'] = max(
                    per_variant[variant]['deterministic_diagnostics_max_abs'],
                    float(np.abs(diagnostics[:, :4] - stored[:, :4]).max()))
                per_variant[variant]['timing_column_max_abs_ms'] = max(
                    per_variant[variant]['timing_column_max_abs_ms'],
                    float(np.abs(diagnostics[:, 4] - stored[:, 4]).max()))
            compared += 1
    finally:
        for expert in experts.values():
            expert.close()

    tolerances = {'states_max_abs': 0.0, 'initial_cost_max_abs': 1e-12}
    for variant in VARIANTS:
        tolerances[variant + '_cost_max_abs'] = 1e-12
        tolerances[variant + '_ends_world_max_abs'] = 1e-12
        tolerances[variant + '_deterministic_diagnostics_max_abs'] = 0.0
    observed = {'states_max_abs': errors['states_max_abs'], 'initial_cost_max_abs': errors['initial_cost_max_abs']}
    for variant in VARIANTS:
        for key, value in per_variant[variant].items():
            observed[variant + '_' + key] = value
    # The wall-time column is re-measured on every run and is explicitly excluded
    # from the pass/fail decision; it is reported so the difference is visible.
    exceeded = {key: value for key, value in observed.items()
                if key in tolerances and value > tolerances[key]}
    timing_only = {key: value for key, value in observed.items()
                   if key.endswith('_timing_column_max_abs_ms')}
    status = 'passed' if (dataset_identity_ok and hashes_ok and not exceeded) else 'failed'
    report = {
        'status': status,
        'scope': 'Independent re-computation of a seeded random sample of the frozen expert test cache; not a new Table-I measurement',
        'cache': str(args.cache.relative_to(ROOT)),
        'samples_requested': args.samples,
        'samples_compared': compared,
        'sample_seed': args.seed,
        'sample_indices': indices.tolist(),
        'dataset_identity_match': dataset_identity_ok,
        'cached_file_hashes': file_hashes,
        'tolerances': tolerances,
        'observed_max_abs': observed,
        'timing_only_differences': timing_only,
        'timing_note': 'Diagnostics column 4 is C++ wall time in ms and is re-measured per run; it is excluded from the pass/fail decision.',
        'tolerance_exceeded': exceeded,
        'wall_seconds': time.perf_counter() - started,
    }
    write_json_atomic(args.cache / 'integrity_audit.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'cached_file_hashes'}, indent=2))
    if status != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
