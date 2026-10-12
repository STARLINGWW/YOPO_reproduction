from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from yopo_repro.forest import generate,signed_distance
from yopo_sim.evaluation_geometry import ForestEvaluator


def test_vectorized_scoring_matches_validated_scene_geometry():
    rng=np.random.default_rng(142)
    for seed in [100,3000]:
        scene=generate(seed);evaluator=ForestEvaluator(scene)
        for p in rng.uniform([-35,-35,-1],[35,35,9],(64,3)):
            np.testing.assert_allclose(evaluator.distance(p),signed_distance(p,scene),atol=1e-12)
