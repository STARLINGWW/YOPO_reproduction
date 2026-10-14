"""Amend a runtime admission record after reviewed runtime-file changes.

The admission record pins the byte hashes of the frozen runtime files; any reviewed,
deliberate edit must therefore be recorded explicitly (transparent amendment), or
future runs will be refused with 'Runtime changed after benchmark validation'.

This tool recomputes the frozen file hashes, updates the record and appends a named
amendment entry. It refuses to run when nothing changed. It never touches evidence.

  python scripts/amend_runtime_admission.py --name reference_arm \
      --scope "official-weight reference arm" --reason "additive provenance-class branch; primary-path behaviour unchanged"
"""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from yopo_repro.io import sha256_file, write_json_atomic
from record_runtime_validation import RUNTIME_FILES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=ROOT / "benchmarks/protocol_v1/runtime_validation.json")
    parser.add_argument("--name", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--effect", default=("Primary-path behaviour is unchanged: all new branches are keyed on the "
                                             "reference provenance class and never activate for primary episodes. "
                                             "Future-run authentication uses the amended hashes."))
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    amended = []
    for name in RUNTIME_FILES:
        path = ROOT / name
        if not path.is_file():
            raise SystemExit("Frozen runtime file missing: " + name)
        digest = sha256_file(path)
        old = record.get("runtime_files", {}).get(name)
        if old != digest:
            amended.append({"path": name, "old_sha256": old, "new_sha256": digest})
        record.setdefault("runtime_files", {})[name] = digest
    if not amended:
        raise SystemExit("No runtime file changed; the admission record is already current")
    key = "runtime_files_amendment" if args.name == "first" else "runtime_files_amendment_" + args.name
    record[key] = {"date": time.strftime("%Y-%m-%d"), "scope": args.scope, "reason": args.reason,
                   "amended": amended, "effect": args.effect}
    write_json_atomic(args.record, record)
    print(json.dumps({"record": str(args.record.relative_to(ROOT)).replace("\\", "/"),
                      "amendment_key": key, "amended_files": len(amended),
                      "paths": [entry["path"] for entry in amended]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
