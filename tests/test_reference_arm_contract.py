"""Contract for the external-reference arm: definition, gates and isolation.

No GPU, no Isaac, no ROS2: the tests check the frozen definitions and the pure
provenance/gating helpers, plus the isolation guarantee that the reference arm can
never leak into the primary summary.
"""
from pathlib import Path
import hashlib
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from yopo_eval.task_spec import resolve_episode, verify_reference_weights

PROTOCOL = ROOT / "benchmarks/reference_arm_official_v1/protocol.json"
PRIMARY_SUMMARY = ROOT / "artifacts/benchmark_summary/summary.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol():
    if not PROTOCOL.is_file():
        pytest.skip("reference-arm protocol not built yet")
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_reference_protocol_mirrors_the_frozen_tasks():
    protocol = load_protocol()
    episodes = protocol["episodes"]
    assert len(episodes) == 300
    assert all(episode["model"] == "yopo_official_reference" for episode in episodes)
    assert sum(1 for episode in episodes if episode.get("paper_first10")) == 100
    for entry in protocol["maps"]:
        assert sha256(PROTOCOL.parent / entry["file"]) == entry["sha256"], entry["file"]
    primary = json.loads((ROOT / "benchmarks/protocol_v1/protocol.json").read_text(encoding="utf-8"))
    primary_tasks = {(task["map_seed"], task["trial"]): task for task in primary["tasks"]}
    for task in protocol["tasks"]:
        mirror = primary_tasks[(task["map_seed"], task["trial"])]
        assert task["condition"] == mirror["condition"] and task["density_per_m2"] == mirror["density_per_m2"]
        assert task["start"] == mirror["start"] and task["goal"] == mirror["goal"]
    mission = resolve_episode(PROTOCOL, episodes[0]["id"])
    assert mission["backend"] == "yopo_reference" and mission["training_seed"] is None


def test_reference_weights_are_hash_pinned_and_reject_tampering(tmp_path):
    protocol = load_protocol()
    reference = protocol["reference_weights"]
    checkpoint = ROOT / "checkpoints" / reference["staged_checkpoint"]
    assert sha256(checkpoint) == reference["staged_sha256"]
    assert sha256(ROOT / "external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth") == reference["source_sha256"]
    verified = verify_reference_weights(ROOT, checkpoint, reference)
    assert verified["provenance_class"] == "external_reference"
    assert "NO from-scratch" in verified["claims"] and "NO validation-selection" in verified["claims"]

    fake = tmp_path / "checkpoints/official_epoch50_reference"
    fake.mkdir(parents=True)
    (fake / "best_policy.pth").write_bytes(b"not the released weights")
    provenance = json.loads((ROOT / reference["provenance_file"]).read_text(encoding="utf-8"))
    provenance_dir = tmp_path / "checkpoints/official_epoch50_reference"
    (provenance_dir / "PROVENANCE.json").write_text(json.dumps(provenance), encoding="utf-8")
    mapping = tmp_path / reference["mapping_record"]
    mapping.parent.mkdir(parents=True)
    mapping.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Reference checkpoint hash mismatch"):
        verify_reference_weights(tmp_path, fake / "best_policy.pth", reference)


def test_primary_summary_is_not_written_by_the_reference_aggregator():
    source = (ROOT / "scripts/aggregate_reference_arm.py").read_text(encoding="utf-8")
    assert 'ROOT / "artifacts/benchmark_summary/summary.json"' in source  # explicit refusal
    assert "reference_arm_official_v1_summary.json" in source
    before = PRIMARY_SUMMARY.read_bytes() if PRIMARY_SUMMARY.is_file() else None
    assert PRIMARY_SUMMARY.is_file()
    assert PRIMARY_SUMMARY.read_bytes() == before


def test_primary_scope_excludes_reference_runs():
    summary = json.loads(PRIMARY_SUMMARY.read_text(encoding="utf-8"))
    assert summary.get("expected_episodes") == 1500
    assert summary.get("active_scope", {}).get("expected_episodes") == 1500
    models = set(summary.get("active_scope", {}).get("models", []))
    assert "yopo_official_reference" not in models
