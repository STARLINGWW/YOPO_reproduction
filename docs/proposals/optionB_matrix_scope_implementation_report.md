# 选项 B 实现预演报告（**补丁已备好，尚未落地**）

记录时间：2026-09-26 (+08:00)
状态：**proposal only / not applied**。本报告与同目录的 `optionB_matrix_scope_implementation.patch` 只是"用户批准后可立即落地"的准备物；仓库中被该补丁涉及的 7 个文件**目前仍是原样**，判据未改、证据未动。

规格来源：`docs/proposals/optionB_matrix_scope_proposal.md`（§2.1–2.5）；判据冲突证据链：`artifacts/environment/completion_criteria_gap.json`。

## 1. 预演环境（隔离沙箱，不触碰真实项目）

- 沙箱：`%TEMP%\yopo_optionb_sandbox_20260926`（本次实测；可随时删除）。
- 复制进沙箱（真实文件）：`scripts/`、`src/`、`tests/`、`configs/`、`benchmarks/`（含 protocol/maps/runtime_validation）、`artifacts/benchmark_summary/*.json`、`artifacts/environment/*.json`、`artifacts/expert/*.json`、`artifacts/paper_sources/mppi_identity.json`、`artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json`。
- 只读链接（junction，避免复制上百 GB）：`artifacts/ros2_flights`、`artifacts/agile_autonomy`、`datasets`。
- 真实权重副本：`checkpoints/formal_main_v1_seed{0,1,2}/{best_policy.pth, training_audit.json, run_manifest.json, result.json}`（含被审计权重 `af2ea0fa…`，供 yopo 逐集校验真实执行 SHA256 比对）。
- **占位说明**：三个种子的 `epoch_*.pt` / `policy_epoch_*.pth` 共 300 个文件在沙箱中用 0 字节占位（终审只做"数量=50/50"检查，不读内容）。因此沙箱里的 `three_seed_training` 只能证明接线，不能替代真实验收；落地后必须在真实项目重跑。

## 2. 沙箱基线（未改动任何代码）

| 步骤 | 结果 |
|---|---|
| `python scripts/final_acceptance_audit.py` | 5 verified + 1 documented_gap + 1 pending（`benchmark_matrix` pending） |
| `python scripts/aggregate_benchmarks.py` | status=`incomplete`、completed=1500 / expected=1800、invalid=0、duplicates=0 |

## 3. 沙箱实测（应用补丁后，真实证据）

| 步骤 | 结果 |
|---|---|
| `python scripts/aggregate_benchmarks.py`（48.5 s） | status=**`outcome_coverage_complete_for_admitted_scope`**、completed=**1500** / admitted=**1500** / expected=1800、missing=0、`excluded_episodes`=**300**（全部 `mppi_reference17`，reason=`not_attempted_backend_unavailable`）、`exclusion_problems`=**[]**、invalid=0、duplicates=0 |
| `python scripts/final_acceptance_audit.py` | **6 verified + 1 documented_gap + 0 pending**（`all_verified=false`，因为 documented_gap 不是 verified，符合既有语义） |
| `benchmark_matrix` 明细 | `completed=1500 of admitted_expected=1500 (frozen protocol expects 1800); excluded_by_policy=300; driver_failures(non-excluded)=0; invalid_evidence=0; duplicates=0; aggregate_status=outcome_coverage_complete_for_admitted_scope; exclusion_reasons=['not_attempted_backend_unavailable']` |
| `python scripts/make_status_overview.py` | 新增两行：`逐槽显式排除 300 槽`、`排除合法性检查 通过（无问题）`；汇总行为 `completed=1500 / admitted=1500 / expected=1800` |

## 4. 测试

| 测试集 | 结果 |
|---|---|
| 终审 + 排除范围反滥用 + 既有聚合（`test_final_acceptance_audit.py`、`test_aggregate_admitted_scope.py`、`test_benchmark_aggregation.py`、`test_benchmark_aggregation_full_scale.py`） | **20 passed** |
| 上述 + 矩阵驱动/任务/证据契约（`test_benchmark_matrix_driver.py`、`test_benchmark_tasks.py`、`test_flight_evidence_contract.py`） | **37 passed** |
| 全库 `pytest tests`（沙箱，另补 `ros2_ws/`） | **95 passed + 20 passed**；唯一 collect error 是 `test_policy_runtime.py` 需要 `torch`（宿主未装 torch，环境限制，与补丁无关） |

5 条反滥用测试（对应提案 §2.4）均已实现并通过：

1. 不合法排除（后端已通过准入，或原因不在允许集合）→ 仍然 pending；
2. 非排除槽位缺一集（1499/1500）→ 仍然 pending；
3. 排除数量必须恰好等于"未通过准入后端"的槽位数（299 / 301 都失败）；
4. `configs/reproduction_protocol.json` 里 `baseline_sources.MPPI.status` 一旦不再含 `reference_only`，`mppi_reference17` 项回落 pending；
5. 合成证据树同时覆盖"1500 全绿 + 300 合法排除 → verified"与"排除后仍有缺失/非法 → pending"。
   另外新增一致性测试：`BACKEND_BY_MODEL` 与冻结解析器 `yopo_eval.task_spec.resolve_episode` 对协议中每个模型给出相同 backend。

## 5. 顺带发现的既有问题（不是本次改动引入）

`tests/test_benchmark_matrix_driver.py::test_execute_requires_admission` 在**未改动任何文件**的纯净副本中就已经失败：它断言"准入记录缺失"，但 `benchmarks/protocol_v1/runtime_validation.json` 现在按设计真实存在（纯净副本实测 `1 failed, 11 passed`）。补丁里附带一处最小修正（让该用例自建不含准入记录的临时协议目录），修正后该文件 12/12 通过。

## 6. 补丁涉及的文件（7 个）

| 文件 | 改动 |
|---|---|
| `src/yopo_eval/aggregate.py` | 新增 `collect_exclusions()`、`BACKEND_BY_MODEL`、`ALLOWED_EXCLUSION_REASONS`；`aggregate()` 支持排除集，新增 `admitted_expected_episodes`/`excluded_episodes`/`exclusion_problems` 与状态 `outcome_coverage_complete_for_admitted_scope`；排除项留在分母、绝不计成功 |
| `scripts/aggregate_benchmarks.py` | 读取 driver ledger 与 runtime admission，调用 `collect_exclusions()`，把排除与问题写入 summary.json |
| `scripts/final_acceptance_audit.py` | `check_matrix` 改为按 admitted scope 判定，并**独立重算**合法排除集合（不信任聚合器自述）；driver failures 只允许排除类 |
| `scripts/make_status_overview.py` | 状态总览展示 executed/admitted/expected 与排除合法性 |
| `tests/test_final_acceptance_audit.py` | 合成树覆盖"1500+300 排除 → verified"、"1800 全执行 → verified"、非法排除/缺集/污染协议 → pending |
| `tests/test_aggregate_admitted_scope.py` | 新增：排除范围反滥用单元测试（含与冻结解析器一致性） |
| `tests/test_benchmark_matrix_driver.py` | 修正上面第 5 节的既有过期用例 |

## 7. 批准后的落地步骤

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'
# 1) 由 Codex 按 optionB_matrix_scope_implementation.patch 修改这 7 个文件（或 git apply -p1 该补丁）
# 2) 只重跑后处理（不重跑矩阵、不重跑任何飞行）
python -m pytest tests/test_final_acceptance_audit.py tests/test_aggregate_admitted_scope.py tests/test_benchmark_aggregation.py tests/test_benchmark_aggregation_full_scale.py tests/test_benchmark_matrix_driver.py -q
python scripts/aggregate_benchmarks.py
python scripts/final_acceptance_audit.py
python scripts/make_status_overview.py
# 3) 更新 artifacts/environment/protocol_snapshot_delta.json（记录本次只改范围/状态元数据）
# 4) 校验 20 文件运行时冻结清单与 benchmarks/protocol_v1/protocol.json 的 SHA256 未变
```

## 8. 残余风险与边界（必须保留在报告口径里）

- 这是一次**验收范围**变更，不是新证据：任何报告都不得声称"已执行 1800 集"；MPPI 的 300 槽始终是"按政策未执行、逐槽显式排除"。
- `mppi_reference17` 项保持 `documented_gap`，依赖 `baseline_sources.MPPI.status` 含 `reference_only`；改动该字段会让终审回落 pending（有反滥用测试保护）。
- `benchmarks/protocol_v1/protocol.json`、20 文件运行时冻结清单、训练与评测参数**均不改**。
- 沙箱用了占位 epoch 文件；真实 `three_seed_training` 证据仍在项目里，落地后重跑终审即为权威结果。
- 本补丁未落地前，仓库终审仍是 `5 verified + 1 documented_gap + 1 pending`。
