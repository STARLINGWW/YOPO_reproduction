"""Build the frozen external-reference-arm protocol (official weights, same task set).

The reference arm reuses the primary protocol's task definitions and map files
byte-for-byte, but registers them under a new model name
(`yopo_official_reference` -> backend `yopo_reference`) in its own directory, so the
frozen primary protocol and its admission record are never touched.

Provenance class `external_reference`: the released official epoch50 weights,
rename-only into the main layout, pinned by SHA256; no from-scratch initialization
claim and no validation-selection claim is made for this arm.

Run once (or to regenerate): python scripts/create_reference_arm_protocol.py
Writes: benchmarks/reference_arm_official_v1/{protocol.json, maps/*.json}
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "benchmarks/protocol_v1/protocol.json"
TARGET = ROOT / "benchmarks/reference_arm_official_v1"
sys.path.insert(0, str(ROOT / "src"))
from yopo_repro.io import sha256_file, write_json_atomic


def main():
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    provenance = json.loads((ROOT / "checkpoints/official_epoch50_reference/PROVENANCE.json").read_text(encoding="utf-8"))
    staged = ROOT / "checkpoints/official_epoch50_reference/best_policy.pth"
    upstream = ROOT / "external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth"
    assert sha256_file(staged) == provenance["staged_sha256"], "staged checkpoint hash changed"
    assert sha256_file(upstream) == provenance["source_sha256"], "upstream checkpoint hash changed"

    TARGET.mkdir(parents=True, exist_ok=True)
    maps = []
    for entry in primary["maps"]:
        source = PRIMARY.parent / entry["file"]
        destination = TARGET / entry["file"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or sha256_file(destination) != entry["sha256"]:
            destination.write_bytes(source.read_bytes())
        assert sha256_file(destination) == entry["sha256"], entry["file"]
        maps.append(dict(entry))

    tasks = [dict(task) for task in primary["tasks"]]
    episodes = []
    for episode in primary["episodes"]:
        if episode["model"] != "yopo_seed0":
            continue
        task = primary["tasks"][episode["task_index"]]
        episodes.append({
            "id": "refofficial_%s_v%d_trial%02d" % (task["condition"], int(episode["speed_mps"]), int(task["trial"])),
            "model": "yopo_official_reference",
            "task_index": episode["task_index"],
            "speed_mps": episode["speed_mps"],
            "paper_first10": bool(episode.get("paper_first10")),
            "timeout_s": episode["timeout_s"],
            "status": "pending",
        })
    episodes.sort(key=lambda e: (e["task_index"], e["speed_mps"]))
    assert len(episodes) == 300 and len({e["id"] for e in episodes}) == 300

    document = {
        "version": 1,
        "status": "reference_arm_definition_frozen",
        "scope": ("official released YOPO weights (external_reference class: hash-pinned, rename-only, "
                  "no from-scratch and no validation-selection claim) on the same Isaac/ROS2 chain, tasks, "
                  "criteria and speeds as the active YOPO-only scope; separate admission record and separate "
                  "summary; never merged into the primary 1,500-slot claims"),
        "paper": primary["paper"],
        "maps": maps,
        "tasks": tasks,
        "episodes": episodes,
        "criteria": dict(primary["criteria"]),
        "reference_weights": {
            "class": "external_reference",
            "source_repository": "TJU-Aerial-Robotics/YOPO (branch YOPO-Simple)",
            "source_commit": provenance["source_commit"],
            "source_sha256": provenance["source_sha256"],
            "staged_checkpoint": "official_epoch50_reference/best_policy.pth",
            "staged_sha256": provenance["staged_sha256"],
            "provenance_file": "checkpoints/official_epoch50_reference/PROVENANCE.json",
            "mapping_record": provenance["mapping_record"],
            "claims": ("hash-pinned released weights; NO from-scratch initialization claim and "
                       "NO validation-selection claim"),
        },
    }
    write_json_atomic(TARGET / "protocol.json", document)
    print(json.dumps({"protocol": str((TARGET / "protocol.json").relative_to(ROOT)).replace("\\", "/"),
                      "episodes": len(episodes), "maps": len(maps),
                      "sha256": sha256_file(TARGET / "protocol.json")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
