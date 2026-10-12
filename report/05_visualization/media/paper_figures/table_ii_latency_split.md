# Table II 延迟分解（4 m/s，两档密度；补充证据）

来源：驱动账本 `artifacts/benchmark_summary/matrix_progress.json` 与 runtime 准入记录关联到的逐 episode `evaluation.json`。
正式口径仍以 `artifacts/benchmark_summary/summary.json` 的准入校验汇总为准；本表补充论文 Table II 需要的 mapping/front/back 分解。

| 模型 | 密度 | n | mapping融合P50 | mapping ESDF P50 | front队列P50 | back规划发布P50 | 取像发布P50 | 端到端P50 | 传输残差P50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| agile_autonomy | dense | 30 | n/a | n/a | 0.20 | 6.96 | 80.93 | 91.73 | 3.35 |
| agile_autonomy | sparse | 30 | n/a | n/a | 0.20 | 7.12 | 81.49 | 92.37 | 3.34 |
| topotraj | dense | 30 | 2.66 | 3.83 | n/a | 0.54 | 83.86 | 173.40 | n/a |
| topotraj | sparse | 30 | 2.51 | 3.64 | n/a | 0.54 | 82.85 | 174.13 | n/a |
| yopo_seed0 | dense | 30 | n/a | n/a | 0.21 | 7.69 | 82.98 | 95.57 | 4.50 |
| yopo_seed0 | sparse | 30 | n/a | n/a | 0.21 | 7.67 | 83.68 | 96.23 | 4.53 |
| yopo_seed1 | dense | 30 | n/a | n/a | 0.20 | 7.58 | 81.23 | 93.53 | 4.33 |
| yopo_seed1 | sparse | 30 | n/a | n/a | 0.20 | 7.60 | 80.09 | 92.41 | 4.33 |
| yopo_seed2 | dense | 30 | n/a | n/a | 0.21 | 7.57 | 80.47 | 92.72 | 4.32 |
| yopo_seed2 | sparse | 30 | n/a | n/a | 0.21 | 7.59 | 80.46 | 92.79 | 4.30 |
