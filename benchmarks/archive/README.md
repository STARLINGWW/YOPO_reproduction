# 历史归档（historical_protocol_v1）

标签：`historical_protocol_v1` / `not_used_by_active_yopo_only_release`。

本目录保存 2026-10-13 冻结 YOPO-only 活动范围之前的原文快照，仅作实验来源与
审计追溯使用，**不表示当前仍待完成**：

- `protocol_v1_1800/plan_1800_pre_release.json`：1800 槽位超集矩阵的调度快照。
- `protocol_v1_1800/summary_1800_pre_release.json`：超集口径的汇总（1500/1800，
  缺口 300 为参考[17] MPPI 未执行槽位；sha256 `18cba378…b2e9`）。
- `protocol_v1_1800/final_acceptance_audit_pre_release.json`：冻结前的终审记录
  （5 verified ＋ 1 documented_gap ＋ 1 pending）。
- `protocol_v1_1800/mppi_reference17_episodes.json`：从冻结协议提取的 300 个
  `mppi_reference17` 槽位清单（附协议 sha256；仅作历史参考，不得重新进入活动矩阵）。

活动范围声明：`benchmarks/protocol_v1/active_scope_yopo_only.json`。

活动口径：

- 活动范围：`../protocol_v1/active_scope_yopo_only.json`（五模型 × 300 = 1500）。
- 逐条证据锚点仍是 `../protocol_v1/protocol.json`（1800 超集，保持字节不变）。
- MPPI 相关资料已归档至 `../../report/90_archive/mppi/` 与
  `../../plan/90_decisions/archive_mppi/`；活动入口不得再把它列为当前待办。

重新生成派生汇总只按活动范围计算覆盖率：

```powershell
python scripts/aggregate_benchmarks.py
```
