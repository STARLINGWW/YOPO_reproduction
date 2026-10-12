# 提案（**未实施，需用户明确批准**）：把主矩阵的覆盖判据冻结为「已验证后端 1500 槽 + 300 个显式排除槽位」

记录时间：2026-09-24 17:15 (+08:00)
状态：**proposal only**。本文件不改变任何代码、判据或证据；在用户明确批准之前不得据此实施。
相关的既知冲突与完整证据链：`artifacts/environment/completion_criteria_gap.json`

## 1. 问题

冻结协议要求主矩阵执行 1800 个槽位（6 个方法 × 300），其中 300 个属于 `mppi_reference17`。该基线没有官方实现（`artifacts/paper_sources/mppi_identity.json`、`mppi_reference17_lookup_20260924_pm.json`），项目政策也禁止用其它 MPPI 项目顶替，因此这 300 槽在执行上不可填充：

- 驱动 `scripts/run_benchmark_matrix.py:275-282` 对它们写 `not_attempted_backend_unavailable`，并把跳过计入 `failures`，最终以非零码退出（`:342-347`）。
- 聚合器只统计真实飞行证据（`scripts/aggregate_benchmarks.py`），覆盖判据要求 `completed == expected == 1800`（`src/yopo_eval/aggregate.py:44-46`）。
- 终审 `scripts/final_acceptance_audit.py:113-130` 要求 `completed==expected==1800 且 failures==0`。

结果：即使其余 1500 槽全部真实执行，`benchmark_matrix` 也**永远停在 pending**。

## 2. 提案内容（若批准）

把"矩阵范围"从"协议里的全部 1800 槽"明确改成"协议里 **runtime admission 已验证后端**的 1500 槽"，并要求 300 个 MPPI 槽位以**逐槽位显式排除**的方式出现在聚合与终审里。任何报告都不得声称"已执行 1800 集"。

### 2.1 `scripts/aggregate_benchmarks.py`

- 读取驱动的 ledger（`artifacts/benchmark_summary/matrix_progress.json`，即 `run_benchmark_matrix.py --progress` 的默认值），收集所有 `not_attempted_*` 记录。
- 只接受满足以下全部条件的排除：该槽位 id 在冻结协议中存在；其 `backend` 不在 `runtime_validation.json` 的 `validated_backends` 中；原因字符串属于允许集合（`not_attempted_backend_unavailable` / `not_attempted_backend_unvalidated`）。
- 把 `record_counts`（真实飞行证据）与 `excluded_documented`（显式排除）一起传给聚合器；`expected_episodes` 仍为协议的 1800，另加 `admitted_expected_episodes`。

### 2.2 `src/yopo_eval/aggregate.py`

- 新增 `excluded_episodes`（逐项含 id/model/reason）与 `admitted_expected_episodes`。
- 新增状态 `outcome_coverage_complete_for_admitted_scope`：仅当**所有非排除槽位都有终态证据**、且**所有排除项都通过 2.1 的合法性检查**时成立；任何其它缺失或任何"不合法排除"一律保持 `incomplete`。
- 分组统计（Wilson 区间、成功/失败分母、可能的最终成功率上下界）继续把**排除项计入分母**或显式标注为未知，不把排除当成功。

### 2.3 `scripts/final_acceptance_audit.py`

- `check_matrix` 改为：`completed == admitted_expected_episodes`、`invalid_evidence == 0`、`duplicate_primary_attempts == 0`、`driver failures` 中**不含**非排除类失败、聚合状态为 admitted-scope 完成态时判 `verified`。
- 该项的 `requirement` / `detail` 文本必须写明"1500 槽已执行 + 300 个 MPPI 槽位按政策显式排除"，并把 `artifacts/environment/completion_criteria_gap.json` 作为并列证据列出。
- MPPI 那一项（`mppi_reference17`）保持现在的 `documented_gap` 判定不变（依赖协议里的 `reference_only…` 字符串）。

### 2.4 反滥用测试（必须与实现同时交付）

1. **不合法排除 → 仍然 pending**：某个被排除槽位的后端其实在 `validated_backends` 中，或原因不在允许集合 → 该项必须仍为 pending。
2. **非排除槽位缺一集 → 仍然 pending**：`completed == admitted_expected - 1` 必须 pending（现有 full-scale 聚合测试的思路，扩到终审层）。
3. **排除数量必须等于协议中该后端的槽位数**：排除 299 或 301 个 MPPI 槽位都要失败；每个被排除 id 必须能在协议里解析出来。
4. **缺口声明必须活着**：把协议里的 `baseline_sources.MPPI.status` 从 `reference_only…` 改成别的值后，该项必须回落到 pending（防止"排除了却不再声明缺口"）。
5. 合成证据树测试（`tests/test_final_acceptance_audit.py`）扩展为同时覆盖"1500 全绿 + 300 合法排除"和上述三种失败路径。

### 2.5 文档与溯源

- `reports/ROS2从头训练执行进度.md`、`reports/复现状态总览.md`、README 中所有涉及矩阵的表述改为"1500 已执行 / 300 按政策排除"，并显式说明这不是论文原始 1800 集的等价复现。
- 改动写进 `artifacts/environment/protocol_snapshot_delta.json`，声明只涉及状态/范围元数据，不改训练与评测参数。
- `configs/benchmark_runtime/v1.json` 与 20 文件运行时冻结列表**不改**。

## 3. 明确不做的事

- 不为 300 个槽位伪造、补写或借用任何飞行证据。
- 不把"排除"计入成功、不用其它 MPPI 实现顶替、不改真实飞行结局。
- 不在没有批准的情况下改判据——本文件只是让批准后可以一次性、可审查地实施。

## 4. 其它两条路（对照）

- **A 补齐槽位**：需要合法论文副本（IEEE 订阅 / NUS 机构库登录下载；公开渠道只有记录、内容端点 HTTP 401）＋研究级实现（运行器的后端枚举、准入表、适配器）＋额外约 4–5 小时 GPU。
- **C 保持现状**：终审如实停在 `benchmark_matrix=pending`，目标不标记完成。

如果选 B，请回复一句明确的批准（例如"批准选项 B：矩阵范围冻结为已验证的 1500 槽，300 个 MPPI 槽位显式排除"），我会按 2.1–2.5 实施并跑通全部测试后再更新判据与文档。
