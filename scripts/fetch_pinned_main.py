"""Fetch text sources for the original YOPO implementation, verifying Git blob IDs.

Uses the already pinned tree manifest; never substitutes a moving branch head.
Existing mismatching files are preserved and reported as errors.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "external/audit_sources"
TREE = json.loads((SOURCE_ROOT / "main_tree.json").read_text())
COMMIT = "881e1c549122efa5a2402b862f70a198e6e93baa"
assert TREE["sha"] == COMMIT


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fetch(item):
    relative = item["path"]
    destination = SOURCE_ROOT / "main" / relative
    try:
        if destination.exists():
            assert git_blob(destination.read_bytes()) == item["sha"], "existing source differs; not overwritten"
            return {"path": relative, "status": "verified-existing"}
        url = f"https://raw.githubusercontent.com/TJU-Aerial-Robotics/YOPO/{COMMIT}/{relative}"
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read()
        assert git_blob(data) == item["sha"], "downloaded Git blob checksum mismatch"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {"path": relative, "status": "downloaded", "git_blob": item["sha"]}
    except Exception as exc:
        return {"path": relative, "status": "error", "reason": str(exc)}


if __name__ == "__main__":
    extensions = {".py", ".cpp", ".cc", ".c", ".h", ".hpp", ".cmake", ".yaml", ".txt", ".md", ".xml"}
    entries = [x for x in TREE["tree"] if x["type"] == "blob" and
               (Path(x["path"]).suffix in extensions or Path(x["path"]).name.startswith("LICENSE")) and
               x.get("size", 0) < 2_000_000]
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(fetch, entries))
    report = {"commit": COMMIT, "files": results,
              "errors": [r for r in results if r["status"] == "error"]}
    output = ROOT / "artifacts/environment"
    output.mkdir(parents=True, exist_ok=True)
    (output / "main_source_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"total": len(results), "errors": report["errors"]}, indent=2))
    raise SystemExit(bool(report["errors"]))
