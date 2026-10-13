"""One-off migration tool: redistribute reports/ into numbered report folders.

Runs inside YOPO_reproduction_new. It copies the detailed reports from the old
`reports/` (and `docs/proposals/`) into the new numbered structure, then
rewrites every Markdown link in the new tree so that

* links that used to target `reports/<name>` now target the new location,
* absolute `D:/.../YOPO_reproduction/...` links become relative links,
* leftover prose mentions of `reports/<name>` are replaced by the new path.

The old project tree is read-only for this script.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

NEW = Path(__file__).resolve().parents[3]
OLD = NEW.parent

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# old project-relative path (posix) -> new project-relative path (posix)
MAPPING = {
    "reports/README.md": "report/00_index/README.md",  # superseded index, no copy
    "reports/当前进度简报.md": "report/01_status/01_当前进度简报.md",
    "reports/复现状态总览.md": "report/01_status/02_复现状态总览.md",
    "reports/YOPO笔记与本地复现逐项对照_2026-10-08.md": "report/02_method/02_YOPO笔记与本地复现逐项对照_2026-10-08.md",
    "reports/原论文与源码差异审计.md": "report/02_method/03_原论文与源码差异审计.md",
    "reports/ROS2从头训练执行进度.md": "report/03_training/01_ROS2从头训练执行进度.md",
    "reports/DAgger聚合与微调方案.md": "report/03_training/02_DAgger聚合与微调方案.md",
    "reports/专家50步比较.md": "report/03_training/03_专家50步比较.md",
    "reports/权重批量对照实验.md": "report/04_evaluation/02_权重批量对照实验.md",
    "reports/权重对比演示实验.md": "report/04_evaluation/03_权重对比演示实验.md",
    "reports/基准运行配置冻结.md": "report/04_evaluation/04_基准运行配置冻结.md",
    "reports/MPPI参考17身份与可得性.md": "report/90_archive/mppi/05_MPPI参考17身份与可得性.md",
    "reports/ROS2基线迁移记录.md": "report/04_evaluation/06_ROS2基线迁移记录.md",
    "reports/演示程序与权重飞行验证命令.md": "report/05_visualization/01_演示程序与权重飞行验证命令.md",
    "reports/完成验收与成果路径.md": "report/90_archive/01_完成验收与成果路径.md",
    "reports/目标完成审计.md": "report/90_archive/02_目标完成审计.md",
    "reports/自训练ROS2闭环阶段报告.md": "report/90_archive/03_自训练ROS2闭环阶段报告.md",
    "reports/YOPO本地复现调研与方案.md": "report/90_archive/04_YOPO本地复现调研与方案.md",
    "reports/YOPO三个任务完整分析报告_2026-10-02.md": "report/90_archive/05_YOPO三个任务完整分析报告_2026-10-02.md",
    "reports/执行手册.md": "report/00_index/02_执行手册.md",
    "reports/implementation_sha256.json": "report/99_artifact_index/implementation_sha256.json",
    "reports/machine_audit.json": "report/99_artifact_index/machine_audit.json",
    "reports/isaac_depth_initial_failure.txt": "report/99_artifact_index/isaac_depth_initial_failure.txt",
    "docs/proposals/optionA_mppi_reference17_plan.md": "plan/90_decisions/archive_mppi/optionA_mppi_reference17_plan.md",
    "docs/proposals/optionB_matrix_scope_proposal.md": "plan/90_decisions/archive_mppi/optionB_matrix_scope_proposal.md",
    "docs/proposals/optionB_matrix_scope_implementation_report.md": "plan/90_decisions/archive_mppi/optionB_matrix_scope_implementation_report.md",
    "docs/proposals/optionB_matrix_scope_implementation.patch": "plan/90_decisions/archive_mppi/optionB_matrix_scope_implementation.patch",
}

LINK = re.compile(r"\]\(([^)\s]+?)\)")
ABS = re.compile(r"^[A-Za-z]:[\\/]")
EXTRA_LOOKUP = {"reports": "report", "docs": "plan/90_decisions/references"}


def posix(path: Path) -> str:
    return path.as_posix()


def copy_sources() -> int:
    copied = 0
    for old_rel, new_rel in MAPPING.items():
        if old_rel == "reports/README.md":
            continue
        source = OLD / old_rel
        target = NEW / new_rel
        if not source.is_file():
            print("missing source:", old_rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def old_location_of(new_rel_file: str) -> str:
    for old_rel, new_rel in MAPPING.items():
        if new_rel == new_rel_file:
            return old_rel
    return new_rel_file


def resolve_old(old_rel_file: str, target: str) -> str | None:
    target = target.strip().strip("<>").split("#", 1)[0]
    if not target:
        return None
    if target.startswith(("http://", "https://", "mailto:", "codex://", "#")):
        return None
    if ABS.match(target):
        normalized = target.replace("\\", "/")
        marker = "/YOPO_reproduction/"
        if marker in normalized and "/YOPO_reproduction_new/" not in normalized:
            return normalized.split(marker, 1)[1]
        return None
    if target.startswith("/"):
        return None
    source_dir = (OLD / old_rel_file).parent
    resolved = (source_dir / target.replace("\\", "/")).resolve()
    try:
        return posix(resolved.relative_to(OLD.resolve()))
    except ValueError:
        return None


def main():
    copied = copy_sources()
    lookup = dict(MAPPING)
    lookup.update(EXTRA_LOOKUP)

    md_files = []
    for base in ("plan", "implement", "report", "benchmarks"):
        md_files += sorted((NEW / base).rglob("*.md"))
    md_files += sorted(NEW.glob("*.md"))

    rewritten_links = 0
    rewritten_absolute = 0
    files_touched = 0

    for path in md_files:
        new_rel_file = posix(path.relative_to(NEW))
        old_rel_file = old_location_of(new_rel_file)
        text = path.read_text(encoding="utf-8")
        changed = False

        def fix(match: re.Match) -> str:
            nonlocal rewritten_links, rewritten_absolute, changed
            target = match.group(1)
            resolved = resolve_old(old_rel_file, target)
            if resolved is None:
                return match.group(0)
            mapped = lookup.get(resolved, resolved)
            fragment = ""
            bare = target.strip().strip("<>")
            if "#" in bare:
                fragment = "#" + bare.split("#", 1)[1]
            import os

            rel_target = os.path.relpath(str(NEW / mapped), str(path.parent)).replace("\\", "/")
            changed = True
            if ABS.match(bare):
                rewritten_absolute += 1
            else:
                rewritten_links += 1
            return "](" + rel_target + fragment + ")"

        text = LINK.sub(fix, text)

        # prose mentions of reports/<name> or docs/proposals/<name>
        def prose(match: re.Match) -> str:
            nonlocal changed
            candidate = match.group(0).lstrip("./").replace("\\", "/")
            for key, value in lookup.items():
                if candidate.endswith(key.split("/")[-1]) and key.startswith(("reports/", "docs/")):
                    changed = True
                    return value
            return match.group(0)

        text = re.sub(r"(?:\.\./)*reports/[^\s)`\"'<>]+\.(?:md|json|txt)", prose, text)
        text = re.sub(r"(?:\.\./)*docs/proposals/[^\s)`\"'<>]+\.(?:md|patch)", prose, text)

        if changed:
            path.write_text(text, encoding="utf-8")
            files_touched += 1

    print(
        {
            "copied": copied,
            "files_touched": files_touched,
            "links_rewritten": rewritten_links,
            "absolute_links_rewritten": rewritten_absolute,
        }
    )


if __name__ == "__main__":
    main()
