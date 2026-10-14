"""Aggregate the external-reference arm separately (never touches the primary summary).

Reads the reference protocol and scans artifacts/ros2_flights for runs whose scope is
`reference_arm_official_v1`, verifies every record against the reference admission and
the pinned checkpoint hash, and writes
artifacts/benchmark_summary/reference_arm_official_v1_summary.json.

The primary aggregator ignores these runs by scope, and this tool never writes the
primary summary.json.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from yopo_eval.aggregate import aggregate, TERMINAL
from yopo_eval.task_spec import resolve_episode, verify_reference_weights
from yopo_repro.io import sha256_file, write_json_atomic

DEFAULT_PROTOCOL = ROOT / "benchmarks/reference_arm_official_v1/protocol.json"
SCOPE = "reference_arm_official_v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/benchmark_summary/reference_arm_official_v1_summary.json")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    assert args.output.resolve() != (ROOT / "artifacts/benchmark_summary/summary.json").resolve(), \
        "Refusing to write the reference arm into the primary summary"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    reference = protocol["reference_weights"]
    admission_path = protocol_path.parent / "runtime_validation.json"
    admission = json.loads(admission_path.read_text(encoding="utf-8")) if admission_path.is_file() else {}

    records, duplicates, invalid, in_flight = {}, [], [], []
    for path in sorted((ROOT / "artifacts/ros2_flights").glob("*/metrics.json")):
        source = json.loads(path.read_text())
        mission = source.get("mission")
        if source.get("scope") != SCOPE or not mission:
            continue
        identity = mission.get("episode_id")
        folder = path.parent
        try:
            resolved = resolve_episode(protocol_path, identity)
            assert mission["protocol_sha256"] == digest and mission["episode"] == resolved["episode"]
            assert json.loads((folder / "scene.json").read_text()) == resolved["scene"]
            assert source["backend"] == "yopo_reference" and source["status"] in TERMINAL
            adm = source.get("runtime_admission") or {}
            assert adm.get("status") == "passed" and adm.get("protocol_sha256") == digest
            assert "yopo_reference" in adm.get("validated_backends", [])
            verified = verify_reference_weights(ROOT, ROOT / "checkpoints" / source["config"]["checkpoint"], reference)
            assert source["checkpoint_sha256"] == verified["checkpoint_sha256"]
            if source["status"] == "crashed":
                assert source.get("traceback"), "Crash lacks diagnostic evidence"
            else:
                validation = json.loads((folder / "validation.json").read_text())
                assert validation["status"] == "passed"
                assert validation["flight_sha256"] == sha256_file(folder / "flight.npz")
                assert validation["checkpoint_sha256"] == source["checkpoint_sha256"]
                assert validation["identity_sha256"] == source["identity_sha256"]
            evaluation = json.loads((folder / "evaluation.json").read_text()) if (folder / "evaluation.json").is_file() else {}
            assert evaluation.get("checkpoint_sha256", source["checkpoint_sha256"]) == source["checkpoint_sha256"]
            samples = []
            with np.load(folder / "flight.npz") as data:
                if data["latencies"].size:
                    samples = (data["latencies"][:, 2] * 1000).tolist()
            if identity in records:
                duplicates.append({"episode_id": identity, "runs": [records[identity]["run"], folder.name]})
                continue
            records[identity] = {"status": source["status"], "run": folder.name, "metrics": evaluation,
                                 "latency_samples_ms": samples}
        except FileNotFoundError as exc:
            # A run that is still being validated right now (the driver writes metrics.json
            # first and runs validate/evaluate afterwards). Only a stale run - missing evidence
            # for longer than the grace window - counts as invalid.
            if time.time() - folder.stat().st_mtime < 15 * 60:
                in_flight.append({"run": folder.name, "episode_id": identity, "note": str(exc)})
            else:
                invalid.append({"run": folder.name, "episode_id": identity, "error": repr(exc)})
        except Exception as exc:
            invalid.append({"run": folder.name, "episode_id": identity, "error": repr(exc)})
    for duplicate in duplicates:
        records.pop(duplicate["episode_id"], None)
    report = aggregate(protocol, records)
    report.update(protocol_sha256=digest, reference_weights={k: reference[k] for k in
                  ("class", "staged_checkpoint", "staged_sha256", "source_sha256", "provenance_file", "mapping_record", "claims")},
                  admission_status=admission.get("status"), duplicate_attempts=duplicates, invalid_evidence=invalid,
                  in_flight_runs=in_flight,
                  isolation_note=("Runs carry scope=%s and are ignored by the primary aggregator; this summary is "
                                  "kept separate from summary.json by construction." % SCOPE))
    if duplicates or invalid:
        report["status"] = "invalid_evidence"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "groups"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
