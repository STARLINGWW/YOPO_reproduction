# DEC-20261013-01：MPPI 移出活动范围，冻结 YOPO-only 1,500 槽归档

日期：2026-10-13 ｜ 状态：已采纳（用户决定） ｜ 关联：[active_scope_yopo_only.json](../../benchmarks/protocol_v1/active_scope_yopo_only.json)、[archive_mppi](archive_mppi/README.md)

## 背景

项目目的聚焦 YOPO 算法复现与迁移验证；参考[17] MPPI 无官方实现，300 槽长期无法产生真实证据，导致 1800/1800 判据无法闭合。

## 决定

1. 活动矩阵冻结为 YOPO-only 五模型 × 300 = 1,500 槽（yopo_seed0/1/2、topotraj、agile_autonomy）；1,500 次已执行结果转为完整覆盖。
2. 参考[17] MPPI 移出活动协议、验收统计与主报告：历史方案归档 `plan/90_decisions/archive_mppi/`，调查记录归档 `report/90_archive/mppi/`；1800 槽超集协议与旧汇总以 `historical_protocol_v1 / not_used_by_active_yopo_only_release` 标签保留在 `benchmarks/archive/`。
3. 固定超集协议 `benchmarks/protocol_v1/protocol.json` 保持字节不变（逐架次证据的 sha256 引用它）；活动范围由 `active_scope_yopo_only.json` 声明，聚合器与终审按其口径执行。
4. 发布路径：现有 GitHub 仓库 `main` 先打存档 tag，再以 v2（本目录）替换；权重与代表媒体走 Git LFS，完整数据/中间检查点走外部归档，SHA256 清单在 `report/06_migration`。

## 影响与边界

- 终审收敛为 6 项全部 verified；报告不得再声称“1800 已执行”，也不得把 MPPI 300 槽列为当前待办。
- 如需重新纳入 MPPI，须新立范围决策并按论文重实现，禁止用其它项目顶替。
- DAgger 收益验证与实机复现仍为研究限制，不随本决定关闭。
