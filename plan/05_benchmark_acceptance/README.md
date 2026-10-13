# 05 基准与验收计划

## 矩阵

2档密度×5档速度×每条件30次×5个活动模型=1,500槽（YOPO-only；1800 槽超集协议保留为 historical_protocol_v1）。已全部执行：622成功、624碰撞、254超时，无效证据0、重复主尝试0。参考[17] MPPI 的 300 槽按 2026-10-13 用户决定移出活动范围并归档。

## 证据规则

每个正式结果必须具有任务身份、运行时哈希、飞行日志、验证和评测证据。无效证据、重复主尝试和measurement gap会阻止无歧义汇总。

## 当前审计

6 verified、0 documented_gap、0 pending、all_verified=true。原 A/B/C 选项随活动范围冻结收敛：B 方向落地为 YOPO-only 活动范围（active_scope_yopo_only.json），A 与 C 停止适用；任何判据变化都不伪造未执行槽位。
