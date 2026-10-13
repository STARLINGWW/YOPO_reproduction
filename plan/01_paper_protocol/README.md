# 01 论文、源码与协议

## 参考来源

- 论文与全文：artifacts/paper_sources/
- main固定源码：external/audit_sources/main/
- Simple固定源码和官方权重：external/audit_sources/YOPO-Simple/
- 运行配置：configs/paper_aligned.json
- 固定矩阵协议：benchmarks/protocol_v1/protocol.json

## 对齐规则

论文中的负代价评分、本地main中的正代价评分、候选筛选和轨迹时域必须分开记录。paper_aligned表示对齐可运行main数值语义，不代表论文所有文字和公开源码逐项一致。

## 当前差异

- Isaac程序化森林替代原Flightmare场景。
- 本地训练使用原版main bucket距离场和主线网络。
- 本地在线选择使用正代价 argmin。
- 参考[17] 全文与身份记录已归档（report/90_archive/mppi/）；MPPI 于 2026-10-13 移出活动范围，不再作为当前缺口。

详细差异见 report/02_method/03_原论文与源码差异审计.md。
