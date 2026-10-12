"""Read-only integrity check for the formal three-seed training metric streams.

For every requested run it parses ``checkpoints/<run>/metrics.jsonl`` and
reports step-sequence continuity, epoch boundaries, loss distributions,
anomalies and checkpoint file counts.  It never opens tensor checkpoints and
never writes outside the requested JSON evidence file, so it is safe to run
while a trainer is live (a growing metrics.jsonl is parsed as-is and the run
status is taken from ``progress.json``/``result.json``).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
LOSS_KEYS = ("total", "trajectory", "score", "gradient_norm_before_clip")


def _load_metrics(path: Path):
    rows, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    return rows, bad


def _run_status(run_dir: Path):
    for name in ("result.json", "progress.json"):
        candidate = run_dir / name
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            return name, payload
    return None, {}


def _payload(row: dict) -> tuple:
    return tuple(row.get(key) for key in LOSS_KEYS)


def _step_continuity(train_rows: list[dict]):
    steps = [row["step"] for row in train_rows if isinstance(row.get("step"), int)]
    seen: dict[int, list[tuple]] = defaultdict(list)
    repeated_identical, repeated_conflicting, negative_deltas = [], [], []
    previous: int | None = None
    for row in train_rows:
        step = row.get("step")
        if not isinstance(step, int):
            continue
        payload = _payload(row)
        if step in seen:
            record = {"step": step, "occurrences": len(seen[step]) + 1}
            (repeated_identical if payload in seen[step] else repeated_conflicting).append(record)
        seen[step].append(payload)
        if previous is not None and step < previous:
            negative_deltas.append({
                "previous_step": previous,
                "current_step": step,
                "identical_replay": payload in seen.get(step, [])[:-1],
            })
        previous = step
    unique = sorted(seen)
    last_step = unique[-1] if unique else None
    missing = [
        step for step in range(unique[0], unique[-1] + 1, 10)
        if step not in seen
    ] if unique else []
    return {
        "rows": len(steps),
        "first_step": unique[0] if unique else None,
        "last_step": last_step,
        "distinct_steps": len(unique),
        "step_size_counts": {str(k): v for k, v in sorted(Counter(
            current - previous for previous, current in zip(steps, steps[1:])
        ).items())},
        "repeated_identical_rows": repeated_identical,
        "repeated_conflicting_rows": repeated_conflicting,
        "backward_jumps": negative_deltas,
        "missing_steps": missing,
    }


def _epoch_stats(rows: list[dict]):
    per_epoch: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        epoch = row.get("epoch")
        if isinstance(epoch, int):
            per_epoch[epoch].append(row)
    boundaries, means, spikes = [], {}, []
    for epoch in sorted(per_epoch):
        bucket = per_epoch[epoch]
        steps = [r["step"] for r in bucket if isinstance(r.get("step"), int)]
        batches = [r["batch"] for r in bucket if isinstance(r.get("batch"), int)]
        totals = [r["total"] for r in bucket if isinstance(r.get("total"), (int, float))
                  and math.isfinite(r["total"])]
        boundaries.append({
            "epoch": epoch,
            "rows": len(bucket),
            "step_min": min(steps) if steps else None,
            "step_max": max(steps) if steps else None,
            "batch_min": min(batches) if batches else None,
            "batch_max": max(batches) if batches else None,
            "batch_restarts_at_one": (min(batches) in (0, 1)) if batches else None,
        })
        if totals:
            means[str(epoch)] = round(statistics.fmean(totals), 9)
            median = statistics.median(totals)
            if median > 0:
                for row in bucket:
                    value = row.get("total")
                    if isinstance(value, (int, float)) and math.isfinite(value) and value > 10 * median:
                        spikes.append({"step": row.get("step"), "total": value, "epoch_median": median})
    return boundaries, means, spikes


def _loss_stats(rows: list[dict]):
    out = {"non_finite": {}, "min": {}, "max": {}, "mean": {}}
    for key in LOSS_KEYS:
        values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        out["non_finite"][key] = sum(1 for v in values if not math.isfinite(v))
        finite = [v for v in values if math.isfinite(v)]
        if finite:
            out["min"][key] = round(min(finite), 9)
            out["max"][key] = round(max(finite), 9)
            out["mean"][key] = round(statistics.fmean(finite), 9)
    return out


def check_run(run: str) -> dict:
    run_dir = PROJECT_ROOT / "checkpoints" / run
    metrics_path = run_dir / "metrics.jsonl"
    if not metrics_path.exists():
        return {"run": run, "error": f"missing {metrics_path}"}
    rows, parse_errors = _load_metrics(metrics_path)
    train_rows = [row for row in rows if row.get("kind") == "train_step"]
    epoch_rows = [row for row in rows if row.get("kind") == "epoch"]
    boundaries, epoch_means, spikes = _epoch_stats(train_rows)
    continuity = _step_continuity(train_rows)
    status_file, status = _run_status(run_dir)
    completed = status.get("epoch_completed")
    if status.get("status") == "complete" and isinstance(status.get("epochs"), int):
        completed = status["epochs"]
    coverage = {"expected_min": None, "expected_max": None, "ok": None}
    if isinstance(completed, int) and continuity["last_step"] is not None:
        coverage["expected_min"] = completed * 6250
        coverage["expected_max"] = completed * 6250 if status.get("status") == "complete" \
            else (completed + 1) * 6250
        coverage["ok"] = coverage["expected_min"] <= continuity["last_step"] <= coverage["expected_max"]
    return {
        "run": run,
        "metrics_path": str(metrics_path.relative_to(PROJECT_ROOT)),
        "metrics_bytes": metrics_path.stat().st_size,
        "parse_errors": parse_errors,
        "status_file": status_file,
        "status": status.get("status"),
        "epochs_completed_reported": status.get("epoch_completed"),
        "epochs_completed_effective": completed,
        "epochs_with_train_rows": len(boundaries),
        "epoch_summary_rows": len(epoch_rows),
        "step_continuity": continuity,
        "epoch_boundaries": boundaries,
        "loss_stats": _loss_stats(train_rows),
        "epoch_mean_total": epoch_means,
        "spikes_gt_10x_epoch_median": spikes,
        "coverage": coverage,
        "file_counts": {
            "epoch_pt": len(list(run_dir.glob("epoch_*.pt"))),
            "policy_pth": len(list(run_dir.glob("policy_epoch_*.pth"))),
            "has_latest_pt": (run_dir / "latest.pt").exists(),
            "has_best_policy": (run_dir / "best_policy.pth").exists(),
            "has_result_json": (run_dir / "result.json").exists(),
            "has_training_audit": (run_dir / "training_audit.json").exists(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reports = [check_run(run) for run in args.runs]
    comparison = {}
    if len(reports) >= 2 and all("epoch_mean_total" in r for r in reports):
        shared = sorted(set(reports[0]["epoch_mean_total"]) & set(reports[1]["epoch_mean_total"]),
                        key=int)
        comparison = {
            "runs": [reports[0]["run"], reports[1]["run"]],
            "shared_epochs": len(shared),
            "mean_total": {
                reports[0]["run"]: round(statistics.fmean(
                    reports[0]["epoch_mean_total"][e] for e in shared), 9) if shared else None,
                reports[1]["run"]: round(statistics.fmean(
                    reports[1]["epoch_mean_total"][e] for e in shared), 9) if shared else None,
            },
        }

    anomalies = []
    for report in reports:
        if report.get("error"):
            anomalies.append(report["error"])
            continue
        continuity = report["step_continuity"]
        if continuity["missing_steps"]:
            anomalies.append(f"{report['run']}: {len(continuity['missing_steps'])} missing step(s)")
        if continuity["repeated_conflicting_rows"]:
            anomalies.append(
                f"{report['run']}: {len(continuity['repeated_conflicting_rows'])} repeated step(s) "
                "with different metrics")
        unexplained = [jump for jump in continuity["backward_jumps"] if not jump["identical_replay"]]
        if unexplained:
            anomalies.append(f"{report['run']}: {len(unexplained)} unexplained backward jump(s)")
        if report["parse_errors"]:
            anomalies.append(f"{report['run']}: {report['parse_errors']} unparsable metric line(s)")
        for key, count in report["loss_stats"]["non_finite"].items():
            if count:
                anomalies.append(f"{report['run']}: {count} non-finite {key} value(s)")
        if report["spikes_gt_10x_epoch_median"]:
            anomalies.append(
                f"{report['run']}: {len(report['spikes_gt_10x_epoch_median'])} spike(s) >10x epoch median")
        if report["coverage"]["ok"] is False:
            anomalies.append(
                f"{report['run']}: last step {continuity['last_step']} outside expected range "
                f"[{report['coverage']['expected_min']}, {report['coverage']['expected_max']}]")
        completed = report["epochs_completed_effective"]
        if isinstance(completed, int) and report["file_counts"]["epoch_pt"] != completed:
            anomalies.append(
                f"{report['run']}: epoch_pt files {report['file_counts']['epoch_pt']} != "
                f"completed epochs {completed}")

    evidence = {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generator": "scripts/check_training_integrity.py",
        "scope": "metrics.jsonl step sequence, epoch boundaries, loss distribution and file counts; "
                 "no tensor checkpoint is opened and no trainer is touched",
        "reports": reports,
        "comparison": comparison,
        "verdict": {
            "status": "passed" if not anomalies else "attention",
            "anomalies": anomalies,
            "note": "duplicate step rows are expected at a resume boundary; inspect their epoch/batch context",
        },
    }
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "verdict": evidence["verdict"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
