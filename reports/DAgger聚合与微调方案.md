# DAgger 聚合数据与微调结果

更新：2026-10-08。**采集、聚合构建、校验、数据暂存和10轮微调均已完成。** 本实验实现的是策略访问观测聚合与独立微调，不是专家动作标注式DAgger，也不宣称完整复制论文未公开脚本。

## 实际执行与证据

| 环节 | 结果 | 证据 |
|---|---|---|
| 采集 | 33架次，18success、15timeout，failures=0 | [flights.json](../artifacts/dagger_flights/dagger_agg_v1/flights.json) |
| 地图 | 11张进入聚合；另5个种子因端点净空不足跳过 | 同上skipped |
| 聚合 | 11个分片，新增7,620样本，status=complete | [aggregation_manifest.json](../datasets/isaac_dagger_v1/aggregation_manifest.json) |
| 微调数据 | 基础100,000＋新增7,620＝107,620训练样本；原验证测试保持不变 | [run_manifest.json](../checkpoints/dagger_main_v1_seed0/run_manifest.json) |
| 微调 | 10轮、67,260步，status=complete、rehearsal=false | [result.json](../checkpoints/dagger_main_v1_seed0/result.json) |
| 起点 | 审计后的seed0最佳权重，SHA256 af2ea0fa… | 同上base_checkpoint_sha256 |

早期日志中16成功/13超时、4个跳过的描述不是最终清单；最终为18成功/15超时、5个跳过地图种子。

## 方法

审计seed0在新地图实际闭环飞行 → 保存策略访问的深度与位姿 → 校验相机、有限值、四元数、帧哈希和地图隔离 → 原版bucket距离场 → 合并基础数据 → 从seed0权重出发微调。基础run没有被覆盖，official_weights_loaded=false、writes_into_base_run=false。

训练沿用轨迹平均代价＋10倍评分SmoothL1损失；新增数据的速度、加速度和目标仍由加载器重新采样。因此补充的是访问位置、朝向和视觉分布，没有专家“正确动作”标签。该工作只完成一轮聚合微调，不代表多轮迭代DAgger。

## 实现入口

- `scripts/run_dagger_collection.py`：采集与地图准入。
- `scripts/build_dagger_dataset.py`、`src/yopo_dagger/build_dataset.py`：独立聚合数据及质量检查。
- `scripts/stage_aggregation_dataset.py`：基础/聚合相对路径暂存。
- `scripts/train_dagger_finetune.py`：独立微调，验证基础权重来源。

现有输出目录不能直接作为新实验重新使用；需要新的run和数据版本。基础数据被相对索引引用，迁移聚合数据时须一并保留基础数据。

## 尚未验证的性能结论

验证损失为0.0229117667，相比基础seed0改善很小。这不证明完整闭环成功率改善。聚合采集只有开发默认稀疏密度；微调权重未进入原三种子正式矩阵。后续需独立、配对的闭环比较，不能把“微调已完成”当成性能提升证据。

原始计划见[dagger_agg_v1_plan.json](../artifacts/dagger_flights/dagger_agg_v1_plan.json)，它的plan_only只表示当时计划文件，不能覆盖后来的complete结果。当前整体状态见[复现状态总览](复现状态总览.md)。
