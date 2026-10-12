# 02 训练流水线

本页覆盖两条链：正式从头训练与 DAgger 聚合微调。算法模块见 [01_core_algorithm](../01_core_algorithm/README.md)；基准矩阵与 300 个 MPPI 槽位缺口不在本页。

## 两条链

```text
正式训练: prepare_dataset → validate_dataset → stage_training_data → train_scratch(容器) → audit_training_run → check_model_selection / audit_resume_readiness
DAgger   : run_dagger_collection → build_dagger_dataset → validate_dataset → stage_aggregation_dataset → train_dagger_finetune
```

## 脚本表

| 脚本 | 作用 | 输入 | 输出 |
|---|---|---|---|
| [scripts/prepare_dataset.py](../../scripts/prepare_dataset.py) | 串行 Isaac 采集＋原版 bucket SDF 构建 | `--name`、`--scale smoke/full`、`--resume` | `datasets/<name>/dataset.json`、`shards/NNN/{scene.json,poses.npz,depth_m.npy,manifest.json,map.json,sdf.npy,pointcloud.ply}` |
| [scripts/collect_isaac_shard.py](../../scripts/collect_isaac_shard.py) | 单个分片：位姿采样＋Isaac 深度采集＋光线 QA | `--output --samples --map-seed --pose-seed --density` | 分片文件与 `manifest.json` |
| [scripts/validate_dataset.py](../../scripts/validate_dataset.py) | 逐帧哈希/位姿/几何回读与 split 隔离 | `--dataset` | 同目录 `validation.json`（status=passed） |
| [scripts/stage_training_data.py](../../scripts/stage_training_data.py) | 校验后的数据复制进 Docker 卷 `/data` | `--name` | `artifacts/environment/data_volume.json` |
| [scripts/train_scratch.py](../../scripts/train_scratch.py) | 确定性、可恢复的从头训练（正式链 50 轮） | `--dataset /data/... --run --seed --epochs --batch-size [--resume]` | run 目录全套检查点、`metrics.jsonl`、`result.json` |
| [scripts/audit_training_run.py](../../scripts/audit_training_run.py) | 单 seed 严格完成审计 | `--run --seed` | run 目录 `training_audit.json` |
| [scripts/training_audit_utils.py](../../scripts/training_audit_utils.py) | 选择复核与状态哈希（只读） | 被上面两个脚本导入 | `verify_model_selection` 结果 |
| [scripts/check_model_selection.py](../../scripts/check_model_selection.py) | best_policy 选择辅助复核 | `--run --expected-epochs` | `artifacts/environment/checkpoint_selection_helper.json` |
| [scripts/audit_resume_readiness.py](../../scripts/audit_resume_readiness.py) | 恢复就绪审计（代码哈希、游标、RNG） | `--run --min-epoch` | `artifacts/environment/formal_checkpoint_window*.json` |
| [scripts/check_resume_equivalence.py](../../scripts/check_resume_equivalence.py) | 断点续训与不间断训练逐位对比 | `--reference --resumed` | `artifacts/environment/resume_equivalence.json` |
| [scripts/check_training_integrity.py](../../scripts/check_training_integrity.py) | 只读检查 metrics 流连续性与异常 | `--runs ... --output ...` | `artifacts/environment/seed_training_integrity_v1.json` |
| [scripts/run_dagger_collection.py](../../scripts/run_dagger_collection.py) | on-policy 闭环采集（真实 PhysX/ROS2 或 `--plan-only`） | `--run --checkpoint --map-seeds --flights-per-map ...` | `artifacts/dagger_flights/<run>/flights.json`＋各架次 `artifacts/ros2_flights/<run>__mX__fNN` |
| [scripts/build_dagger_dataset.py](../../scripts/build_dagger_dataset.py) → [src/yopo_dagger/build_dataset.py](../../src/yopo_dagger/build_dataset.py) | 校验架次并构建聚合数据集版本 | `--base --flights --output --allow-map-seeds --qa-frames --self-check-frame` | `datasets/isaac_dagger_v1/`＋`aggregation_manifest.json` |
| [scripts/stage_aggregation_dataset.py](../../scripts/stage_aggregation_dataset.py) | 聚合数据进卷（要求 base 已 staged 且哈希一致） | `--name --base-name` | `artifacts/environment/aggregation_volume.json` |
| [scripts/train_dagger_finetune.py](../../scripts/train_dagger_finetune.py) | 从已审计 base 权重做微调 | `--dataset /data/isaac_dagger_v1 --run --seed --epochs --base-run` | 独立 run 目录（scope 标注为微调） |

## 正式训练链要点

1. `prepare_dataset.py --scale full` 生成 20×5000 train＋4×2500 valid＋4×2500 test＝100,000/10,000/10,000；每个分片的地图种子唯一，SDF 由容器内参考实现（`original_main_bucket`）生成并记录 SHA256。
2. `validate_dataset.py` 通过后，`run_formal_training.ps1` 会先校验 `validation.json`（counts 必须为 100000/10000/10000），再 staging、建源快照、按 seed0/1/2 串行训练并逐 seed 审计。
3. `train_scratch.py` 新 run 必须位于 `checkpoints/` 下、全新随机初始化；恢复时 `checkpoint['config'] != config` 直接拒绝（config 含 seed/epochs/batch/device/profile/trajectory/`dataset_sha256`/`code_sha256`/torch 版本/样本数），并恢复 Python/NumPy/Torch/CUDA 全部 RNG 状态。
4. 运行产物：`run_manifest.json`、`initial_policy.pth`、`latest.pt`、`epoch_NNN.pt`、`policy_epoch_NNN.pth`、`best_policy.pth`、`metrics.jsonl`、`progress.json`、`tensorboard/`、`result.json`；`best_policy.pth` 只在验证损失严格更优的 epoch 导出。
5. `audit_training_run.py` 断言 50 epochs＝312,500 steps、每个 epoch 检查点与导出权重张量哈希一致、优化器状态有限且 lr=1.5e-4、初始化与结果哈希相符，然后写 `training_audit.json`。

## DAgger 链要点

- 采集前 `run_dagger_collection.py` 会拒绝正式/验证/测试/基准地图种子（100–119、1000–1003、2000–2003、3000、5000–6009），并要求正式训练员已释放 GPU；`--plan-only` 只写计划、不启动 Isaac。
- 每个架次都是带 scope 标记 `dagger_aggregation_rollout_not_benchmark` 的真实闭环运行；构建器逐架次校验相机几何、单位四元数、深度范围、逐帧哈希与独立光线 QA。
- 聚合数据集把 on-policy 帧写入新分片（当前 11 个地图、33 架次、7,620 帧），base 分片以相对路径引用且逐字节不变；valid/test 分片与基础数据集逐字节一致。
- 微调拒绝写入 base run，并要求 base run 已有 passed 审计且 `best_policy.pth` 文件哈希等于审计记录；`result.json` 带 `scope=dagger_aggregation_finetune_not_formal_seed`，不进入原 1800 矩阵。

## 现有产物

- `datasets/isaac_full_v1`：100K/10K/10K，`validation.json` passed。
- `datasets/isaac_dagger_v1`：`scale=dagger_aggregation`，`aggregation_manifest.json` complete。
- `datasets/smoke_v1`、`calibration_v1/v2`：冒烟与标定用小数据集。
- `checkpoints/formal_main_v1_seed{0,1,2}`：50 轮/312,500 步、`training_audit.json` passed；最佳轮次 50/47/50。
- `checkpoints/dagger_main_v1_seed0`（10 轮微调）、`checkpoints/dagger_rehearsal_seed0`（缩减演练）、`checkpoints/resume_*`（恢复等价性证据）、`checkpoints/official_epoch50_reference`（官方权重参考，部署对照用）。
- 证据 JSON：`artifacts/environment/{data_volume,aggregation_volume,resume_equivalence,seed_training_integrity_v1,checkpoint_selection_helper}.json`。

## 运行命令

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'

# 端到端正式链（校验数据门→staging→seed0/1/2 训练→审计）
./scripts/run_formal_training.ps1 -DatasetName isaac_full_v1 -RunPrefix formal_main_next

# 单步（训练与审计脚本以 /workspace、/data 为根，必须走容器）
docker compose --profile training run --rm train python3 scripts/stage_training_data.py --name isaac_full_v1
docker compose --profile training run --rm --name yopo-formal-seed0 train python3 scripts/train_scratch.py --dataset /data/isaac_full_v1 --run formal_main_v1_seed0 --seed 0 --epochs 50 --batch-size 16
docker compose --profile training run --rm train python3 scripts/audit_training_run.py --run formal_main_v1_seed0 --seed 0

# DAgger 计划（不启动 Isaac/GPU，可用主机 Python）
python scripts/run_dagger_collection.py --run dagger_agg_v1 --checkpoint formal_main_v1_seed0/best_policy.pth --map-seeds 7000-7015 --flights-per-map 3 --plan-only

# DAgger 构建（主机 Python，参考 SDF 走 docker）与微调（容器）
python scripts/build_dagger_dataset.py --base datasets/isaac_full_v1 --flights artifacts/dagger_flights/dagger_agg_v1 --output datasets/isaac_dagger_v1 --allow-map-seeds 7000-7015 --qa-frames 30 --self-check-frame 0
docker compose --profile training run --rm --name yopo-dagger-seed0 train python3 scripts/train_dagger_finetune.py --dataset /data/isaac_dagger_v1 --run dagger_main_v1_seed0 --seed 0 --epochs 10 --base-run formal_main_v1_seed0

# 编排入口：-Stages dagger 会按固定顺序执行采集/构建/校验/staging/微调
./scripts/run_post_training_pipeline.ps1 -Stages dagger
```

## 契约与不变量

- 新 run 永远随机初始化整个网络，`official_weights_loaded=false`；训练器从不读取官方权重。
- 恢复只接受本 run 自己的检查点，且代码/数据/torch/配置哈希完全一致；模型、优化器、样本游标与全部 RNG 状态逐位恢复。
- `best_policy.pth` 是验证集最优 epoch 的边界导出；平局取最早 epoch（`verify_model_selection` 复核）。
- 地图隔离与哈希链：train 100–119 / valid 1000–1003 / test 2000–2003 / DAgger 7000–7015；`dataset.json` → shard `manifest_sha256`/`map_sha256` → 各文件 SHA256。
- 审计脚本硬编码 50 轮、312,500 步、batch 16、lr 1.5e-4 契约；契约变化必须同步更新审计与 plan 记录。

## 测试

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'
python -m pytest -q tests/test_dagger_pipeline.py tests/test_dagger_collection_plan.py tests/test_policy_runtime.py

# 只读完整性检查（不打开张量检查点，可在训练进行时运行）
python scripts/check_training_integrity.py --runs formal_main_v1_seed0 formal_main_v1_seed1 formal_main_v1_seed2 --output artifacts/environment/seed_training_integrity_v2.json
```

若默认临时目录不可写，追加 `--basetemp=.pytest_basetemp/<name>`；test_policy_runtime 需 torch 环境，其余两条为 CPU-only。

## 已知限制

- 真实训练、staging 与审计脚本的根目录是容器内 `/workspace`（数据卷 `/data`），不能在主机直接运行；主机侧只保证 `--plan-only`、构建与只读检查可用。
- 训练镜像 `yopo-repro:train-cu128-jammy` 需要 Docker Linux engine 与可用 GPU（`train` profile 声明 `gpus: all`）。
- DAgger 微调权重不是第四个正式 seed，也不进入原 1800 矩阵；其闭环收益需要另做独立比较。
- 恢复等价性证据目前覆盖 1 轮/126 步的逐位一致；更长跨度的逐位等价未单独留证。
- 正式矩阵仍缺 300 个 MPPI 槽位，属基准验收范围，见 [report/04_evaluation/05_MPPI参考17身份与可得性.md)。

## 相关入口

- 数据版本与训练计划：[plan/03_dataset_training](../../plan/03_dataset_training/README.md)
- 训练交付摘要：[report/03_training](../../report/03_training/README.md)
- 命令手册与权重验证合集：[report/00_index/02_执行手册.md)、[report/05_visualization/01_演示程序与权重飞行验证命令.md)
- 基准矩阵与验收（含 MPPI 缺口）：[plan/05_benchmark_acceptance](../../plan/05_benchmark_acceptance/README.md)

