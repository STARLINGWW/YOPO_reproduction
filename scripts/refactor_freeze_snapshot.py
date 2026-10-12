"""Create a refactor freeze snapshot (plan phase 0): protected hashes and sizes.

Read-only with respect to evidence: hashes the protocol/acceptance files,
verifies each best_policy.pth against the hash recorded by its training audit,
and records dataset/checkpoint directory sizes. Writes one JSON snapshot for
migration and rollback reference; it is not an experiment result.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from yopo_repro.io import sha256_file, write_json_atomic

PROTECTED_FILES = [
    "benchmarks/protocol_v1/protocol.json",
    "benchmarks/protocol_v1/runtime_validation.json",
    "artifacts/environment/final_acceptance_audit.json",
    "artifacts/benchmark_summary/summary.json",
    "artifacts/environment/status_overview.json",
    "artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json",
]

RUN_DIRS = [
    "checkpoints/formal_main_v1_seed0",
    "checkpoints/formal_main_v1_seed1",
    "checkpoints/formal_main_v1_seed2",
    "checkpoints/dagger_main_v1_seed0",
]

DATA_DIRS = [
    "datasets/isaac_full_v1",
    "datasets/isaac_dagger_v1",
    "datasets/smoke_v1",
]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def dir_stats(path: Path):
    files = 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            files += 1
            total += item.stat().st_size
    return {"files": files, "bytes": total}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/refactor_20261012/freeze_snapshot.json")
    args = parser.parse_args()

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        head = None

    protected = []
    for rel in PROTECTED_FILES:
        path = ROOT / rel
        protected.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else None,
            }
        )

    runs = []
    for rel in RUN_DIRS:
        folder = ROOT / rel
        policy = folder / "best_policy.pth"
        audit = read_json(folder / "training_audit.json") or {}
        recorded = (audit.get("selection") or {}).get("best_policy_file_sha256")
        actual = sha256_file(policy) if policy.is_file() else None
        runs.append(
            {
                "path": rel,
                "stats": dir_stats(folder) if folder.is_dir() else None,
                "best_policy_exists": policy.is_file(),
                "best_policy_sha256": actual,
                "audit_recorded_sha256": recorded,
                "audit_match": (actual == recorded) if (actual and recorded) else None,
            }
        )

    datasets = []
    for rel in DATA_DIRS:
        folder = ROOT / rel
        datasets.append(
            {"path": rel, "exists": folder.is_dir(), "stats": dir_stats(folder) if folder.is_dir() else None}
        )

    doc_counts = {}
    for rel in ("plan", "implement", "report"):
        folder = ROOT / rel
        doc_counts[rel] = {"markdown_files": len(list(folder.rglob("*.md"))) if folder.is_dir() else 0}

    snapshot = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "scope": "refactor freeze snapshot: protected hashes, audited weights, dataset/checkpoint sizes; not an experiment result",
        "git_head": head,
        "protected_files": protected,
        "weights": runs,
        "datasets": datasets,
        "doc_counts": doc_counts,
    }
    write_json_atomic(ROOT / args.output, snapshot)
    print(
        json.dumps(
            {"generated_at": snapshot["generated_at"], "git_head": snapshot["git_head"], "doc_counts": doc_counts},
            ensure_ascii=False,
        )
    )
    print("wrote", args.output)


if __name__ == "__main__":
    main()
