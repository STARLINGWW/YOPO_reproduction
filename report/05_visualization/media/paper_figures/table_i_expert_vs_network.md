# Table I 对照（专家50步 vs 随机初始化 vs 自训练网络）

来源：`artifacts/expert/` 下的对比 JSON（显式重建的专家口径，非未公开论文脚本的等价声明）。

| 来源 | 15条候选平均代价 | 15条最优平均代价 | 与专家最优候选一致率 | 位置误差均值(m) | 位置误差P95(m) | 采样预算 |
|---|---:|---:|---:|---:|---:|---:|
| random_initial | 0.082267 | 0.039556 | 0.1486 | 1.6860 | 2.7650 | 15 candidates, single forward pass (no optimizer) |
| trained | 0.023105 | 0.017892 | 0.2252 | 2.0738 | 3.2059 | 15 candidates, single forward pass (no optimizer) |
| trained_seed0 | 0.023062 | 0.017855 | 0.2261 | 2.0942 | 3.2069 | 15 candidates, single forward pass (no optimizer) |
| trained_seed1 | 0.023073 | 0.017867 | 0.2238 | 2.0844 | 3.2570 | 15 candidates, single forward pass (no optimizer) |
| trained_seed2 | 0.023072 | 0.017882 | 0.2204 | 2.1014 | 3.2074 | 15 candidates, single forward pass (no optimizer) |
| expert:scaled_gd50 | 0.024253 | 0.021824 | - | - | - | 326.0次目标函数评估均值 |
| expert:mma50_evaluations | 0.021451 | 0.018753 | - | - | - | 50.0次目标函数评估均值 |

