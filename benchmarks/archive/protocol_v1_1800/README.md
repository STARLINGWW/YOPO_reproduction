# protocol_v1_1800 历史归档

标签：`historical_protocol_v1` / `not_used_by_active_yopo_only_release`。

本目录保留 YOPO-only 范围冻结（2026-10-13）前的 1800 槽口径快照，供追溯：

- `summary_1800_pre_release.json`：冻结前的覆盖汇总（当时 1500/1800，缺 300 为 MPPI 未执行）。
- `plan_1800_pre_release.json`：冻结前的调度计划快照（pending=310 为历史值）。
- `final_acceptance_audit_pre_release.json`：冻结前终审（5 verified、1 documented_gap、1 pending）。
- `mppi_reference17_episodes.json`：从冻结协议中提取的 300 个 `mppi_reference17` 槽位清单（含协议 sha256 与排除说明）。

当前活动口径见 `../protocol_v1/active_scope_yopo_only.json`；冻结的 1800 超集协议本体保留在 `../protocol_v1/protocol.json`（字节不可变，作为全部已记录飞行的证据锚点）。
