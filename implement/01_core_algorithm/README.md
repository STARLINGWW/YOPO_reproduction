# 01 核心算法

- 网络与候选解码：external/audit_sources/main/flightpolicy/yopo。
- 本地训练封装：src/yopo_repro/policy.py。
- 五次多项式：src/yopo_repro/quintic.py。
- 轨迹代价与距离梯度：src/yopo_repro/main_cost.py。
- 地图查询：src/yopo_repro/maps.py。

当前本地main采用正代价并用argmin选择；论文文字中的负评分、候选筛选和本地运行差异见report/02_method和reports/原论文与源码差异审计.md。

