"""Two-phase runtime admission for the external-reference arm (official weights).

Mirrors scripts/record_runtime_validation.py, but scoped to the reference protocol
and the `yopo_reference` backend only:
  phase A  a development-scope flight (dev map 3200) with the reference weights;
  phase B  two real reference episodes through the episode-id path.
Writes benchmarks/reference_arm_official_v1/runtime_validation.json.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from yopo_repro.io import write_json_atomic
import record_runtime_validation as primary

BACKEND = {"backend": "yopo_reference", "device": "cuda", "model": "yopo_official_reference",
           "checkpoint": "official_epoch50_reference/best_policy.pth"}
DEFAULT_PROTOCOL = ROOT / "benchmarks/reference_arm_official_v1/protocol.json"


def run_native(run_name, extra):
    command = [primary.require_isaac_python(), str(ROOT / "scripts/run_ros2_navigation.py"),
               "--run", run_name, "--protocol", str(PROTOCOL), "--backend", BACKEND["backend"],
               "--device", BACKEND["device"], "--checkpoint", BACKEND["checkpoint"]] + list(extra)
    log = ROOT / "artifacts/environment" / (run_name + ".log")
    env = primary.os.environ.copy()
    env["OMNI_KIT_ACCEPT_EULA"] = "YES"
    with log.open("a", encoding="utf-8") as handle:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
    steps = {}
    for name, script in [("validate", "scripts/validate_ros2_flight.py"), ("evaluate", "scripts/evaluate_ros2_flight.py")]:
        outcome = subprocess.run([primary.require_isaac_python(), str(ROOT / script), "--run", run_name],
                                 cwd=ROOT, capture_output=True, text=True)
        (ROOT / "artifacts/environment" / (run_name + "_" + name + ".log")).write_text(
            outcome.stdout + outcome.stderr, encoding="utf-8")
        steps[name + "_returncode"] = int(outcome.returncode)
    return {"returncode": int(completed.returncode), "log": str(log.relative_to(ROOT).as_posix()), **steps}


def main():
    global PROTOCOL
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--phase", choices=["a", "b", "ab"], default="ab")
    parser.add_argument("--dev-map-seed", type=int, default=3200)
    parser.add_argument("--dev-speed", type=float, default=2.)
    parser.add_argument("--dev-duration", type=float, default=20.)
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--stamp", default=time.strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    PROTOCOL = args.protocol.resolve()
    primary.require_training_gpu_released()
    protocol_raw = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_raw)
    reference = protocol["reference_weights"]
    admission_path = PROTOCOL.parent / "runtime_validation.json"
    record = {"version": 1, "status": "pending", "protocol_sha256": hashlib.sha256(protocol_raw).hexdigest(),
              "validated_backends": [], "validated_backend_keys": [], "runtime_files": primary.runtime_file_hashes(),
              "phase_a": {}, "phase_b": {}, "consumed_episode_ids": [],
              "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "scope": "native Isaac/ROS2 runtime admission for the external-reference arm; not a success-rate result",
              "rule": ("validated_backends lists the mission backend name used by the reference protocol "
                       "(yopo_reference); released weights are admitted under the external_reference class "
                       "(hash-pinned, rename-only, no from-scratch and no validation-selection claim)"),
              "reference_weights": {"class": reference["class"], "staged_checkpoint": reference["staged_checkpoint"],
                                    "staged_sha256": reference["staged_sha256"], "source_sha256": reference["source_sha256"],
                                    "provenance_file": reference["provenance_file"],
                                    "mapping_record": reference["mapping_record"], "claims": reference["claims"]}}
    failures = []
    if "a" in args.phase:
        run_name = "rv_ref_dev_%s" % args.stamp
        result = run_native(run_name, ["--map-seed", str(args.dev_map_seed), "--speed", str(args.dev_speed),
                                       "--duration", str(args.dev_duration), "--scope",
                                       "runtime_validation_admission_not_matrix_reference"])
        entry = {"run": run_name, **result, "scope": "development_runtime_admission_reference"}
        try:
            entry["evidence"] = primary.verify_run(run_name, "yopo_reference")
        except RuntimeError as exc:
            entry["problems"] = str(exc)
            failures.append("phase A: %s" % exc)
        record["phase_a"]["yopo_reference"] = entry
        if "evidence" in entry and int(entry.get("evaluate_returncode", 1)) == 0:
            record["validated_backends"] = ["yopo_reference"]
            record["validated_backend_keys"] = ["yopo_reference"]
            record["status"] = "passed"
            record["provisional"] = True
        write_json_atomic(admission_path, record)
        if failures:
            raise SystemExit("Reference phase A failed; admission record left provisional/failed")
    if "b" in args.phase:
        existing = json.loads(admission_path.read_text(encoding="utf-8"))
        if existing.get("status") != "passed":
            raise SystemExit("Phase B requires a passed phase-A admission record")
        record = existing
        record["provisional"] = False
        for episode in primary.pick_episodes(protocol, BACKEND["model"], args.episodes):
            run_name = "rv_ref_frozen_%s_%s" % (episode["id"], args.stamp)
            result = run_native(run_name, ["--episode-id", episode["id"]])
            entry = {"run": run_name, "episode_id": episode["id"], "speed_mps": episode["speed_mps"], **result}
            try:
                entry["evidence"] = primary.verify_run(run_name, "yopo_reference")
                record["consumed_episode_ids"].append(episode["id"])
            except RuntimeError as exc:
                entry["problems"] = str(exc)
                failures.append("phase B %s: %s" % (episode["id"], exc))
            record["phase_b"][episode["id"]] = entry
            write_json_atomic(admission_path, record)
        record["status"] = "passed" if not failures else "failed"
        record["failures"] = failures
        record["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        write_json_atomic(admission_path, record)
    print(json.dumps({"status": record["status"], "validated_backends": record["validated_backends"],
                      "consumed_episode_ids": record["consumed_episode_ids"], "failures": failures},
                     indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit("Reference runtime admission failed; the reference matrix must not start")


if __name__ == "__main__":
    main()
