# 03 训练交付

更新：2026-10-12 ｜ 论文对应：II-B 训练策略（Guidance Learning）+ III-A 训练策略验证

## 数据

| 数据集 | 规模 | 构成 | 校验 |
|---|---|---|---|
| [datasets/isaac_full_v1](../../datasets/isaac_full_v1) | 100,000 训练 / 10,000 验证 / 10,000 测试 | 20 + 4 + 4 张地图，按地图隔离 | [validation.json](../../datasets/isaac_full_v1/validation.json)：`status=passed`，全量深度帧、位姿与哈希已核，`dataset_sha256=ee0330a7…` |
| [datasets/isaac_dagger_v1](../../datasets/isaac_dagger_v1) | 7,620 新增样本（11 张地图） | 33 架次访问观测聚合 | [aggregation_manifest.json](../../datasets/isaac_dagger_v1/aggregation_manifest.json)：`status=complete`，基础 shard 哈希逐一比对 |

数据由 Isaac 程序化森林采集（等效条件实验，非 Flightmare 原数据）；采集与校验命令见 [implement/02 训练流水线](../../implement/02_training_pipeline/README.md)。

## 正式训练（三种子）

三个 seed 各 50 轮、312,500 步，随机初始化、从头训练，全部通过逐轮严格审计（审计权重与 `best_policy.pth` 哈希一致）：

| run | 轮数 / 步数 | 最佳轮次 | 最佳验证损失 | 证据 |
|---|---|---|---|---|
| formal_main_v1_seed0 | 50 / 312,500 | 50 | 0.022929 | [training_audit.json](../../checkpoints/formal_main_v1_seed0/training_audit.json) |
| formal_main_v1_seed1 | 50 / 312,500 | 47 | 0.022935 | [training_audit.json](../../checkpoints/formal_main_v1_seed1/training_audit.json) |
| formal_main_v1_seed2 | 50 / 312,500 | 50 | 0.022938 | [training_audit.json](../../checkpoints/formal_main_v1_seed2/training_audit.json) |

训练器不加载专家缓存：专家轨迹只用于离线比较，不参与监督（见 [方法对照](../02_method/01_paper_to_code.md) 差异 D10）。

## DAgger 聚合微调（论文外的本地扩展）

- 33 架次 / 11 张地图访问数据，新增 7,620 样本；从 seed0 微调 10 轮、67,260 步。
- 采集飞行结果：18 成功 / 15 超时；5 个地图 seed 被跳过。
- 结果与清单：[checkpoints/dagger_main_v1_seed0/result.json](../../checkpoints/dagger_main_v1_seed0/result.json)。
- 它是独立微调，不是第四个正式 seed，不进入原 1800 矩阵；现有证据不支持“微调一定改善闭环成功率”。

## 详细报告

- [ROS2从头训练执行进度](../../reports/ROS2从头训练执行进度.md)：带日期的执行日志。
- [DAgger聚合与微调方案](../../reports/DAgger聚合与微调方案.md)：采集、聚合与微调全过程。
- [专家50步比较](../../reports/专家50步比较.md)：三种子权重与专家的离线对照。
- [笔记与本地实现逐项对照](../../reports/YOPO笔记与本地复现逐项对照_2026-10-08.md)：训练图计算核查。

## 相关入口

- [模块总图](../00_index/01_module_map.md) ｜ [02 方法对照](../02_method/README.md) ｜ [04 评测](../04_evaluation/README.md)
- [implement/02 训练流水线](../../implement/02_training_pipeline/README.md)：脚本级代码地图与命令。

