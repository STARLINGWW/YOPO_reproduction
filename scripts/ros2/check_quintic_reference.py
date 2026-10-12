"""Compare our numerical matrices with the unmodified compiled C++ upstream."""
from pathlib import Path
import json
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from yopo_repro.quintic import matrices

results = []
for duration in [.5, 8 / 6, 10 / 6, 5.]:
    reference = json.loads(subprocess.check_output(
        ["ros2", "run", "yopo_math_reference", "matrix_reference", str(duration)], text=True))
    errors = {}
    for name, local in zip(["L", "H", "R"], matrices(duration)):
        expected = np.asarray(reference[name])
        np.testing.assert_allclose(local, expected, rtol=1e-10, atol=1e-8)
        errors[name] = float(np.max(np.abs(local - expected)))
    results.append({"duration": duration, "max_abs_errors": errors})
report = {"status": "passed", "scope": "quintic mapping and jerk matrices only; not complete trajectory loss", "cases": results}
output = ROOT / "artifacts/environment/quintic_cpp_parity.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
