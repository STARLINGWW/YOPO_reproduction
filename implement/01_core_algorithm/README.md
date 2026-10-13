# 01 核心算法

本页是核心算法的实施地图：入口、输入、输出、依赖、测试与已知限制，不复制源码。训练如何消费这些模块见 [02_training_pipeline](../02_training_pipeline/README.md)。

## 模块总览

| 代码 | 职责 | 入口 | 主要输出 |
|---|---|---|---|
| [src/yopo_repro/policy.py](../../src/yopo_repro/policy.py) | 官方 main 网络封装、观测布局、候选解码、指导梯度接入与损失 | `build_policy`、`MapBank.evaluate`、`losses` | `YopoPolicy`、候选代价 `[B,15]`、可反传损失 |
| [src/yopo_repro/main_cost.py](../../src/yopo_repro/main_cost.py) | `GradTrajOptimizer` 代价与梯度的批量数值移植 | `cost_and_gradient`、`CostConfig` | 代价 `[B]`、世界系梯度 `[B,3,3]` |
| [src/yopo_repro/quintic.py](../../src/yopo_repro/quintic.py) | 五次多项式边界值问题与 jerk 积分矩阵 | `Quintic`、`matrices` | 系数、L/H/R 矩阵、端点梯度 |
| [src/yopo_repro/maps.py](../../src/yopo_repro/maps.py) | 表面点云 → ESDF 与体素查询 | `surface_points`、`pointcloud_esdf`、`VoxelSDF` | 距离场数组、最近格点值与差分梯度 |
| [src/yopo_repro/forest.py](../../src/yopo_repro/forest.py) | 程序化森林几何、解析距离/光线查询、USD 场景生成 | `generate`、`signed_distance`、`ray_depth`、`author_scene` | 场景 JSON、光线深度、Isaac USD stage |
| [src/yopo_repro/dataset.py](../../src/yopo_repro/dataset.py) | 地图隔离的深度/位姿 mmap 数据集与确定性状态采样 | `ForestDataset`、`stack_batch` | 训练批次 `(depth,pos,R,obs,map_id)` |
| [src/yopo_repro/io.py](../../src/yopo_repro/io.py) | 哈希与原子 JSON 写 | `sha256_file`、`write_json_atomic` | SHA256、原子 JSON |
| [external/audit_sources/main](../../external/audit_sources/main) | 固定版官方 main 源码（commit `881e1c54…`） | `flightpolicy.yopo.YopoPolicy` | 未修改的网络、原语与可微解码 |

## 数据流（训练一步）

```text
dataset: depth[1,96,160] + pos[3] + R[3,3] + obs[9]
  └─ prepare_observation      归一化并用反转的栅格索引变到 15 个原语坐标系 → [B,9,3,5]
policy(depth, prepared)
  └─ YopoPolicy.forward       → [B,10,3,5]：前 9 通道 tanh 为终端状态参数，第 10 通道 relu 为预测代价
decode_all                    → [B,15,9] 各原语终端状态（id = 14 - i）
MapBank.evaluate              世界系变换＋bucket SDF 查询 → cost_and_gradient → [B,15] 代价与 body 系梯度
GuidanceCost                  自定义 autograd.Function，把地图指导梯度接回网络
losses                        total = 1.0 * mean(J) + 10.0 * SmoothL1(score, J.detach())
```

权重与 profile 来自 [configs/paper_aligned.json](../../configs/paper_aligned.json)；训练循环见 [02_training_pipeline](../02_training_pipeline/README.md)。

## policy.py

- `build_policy(device)`：读 `configs/paper_aligned.json` 与 `external/audit_sources/main/flightlib/configs/traj_opt.yaml`，构造 `YopoPolicy(observation_dim=9, action_dim=9, hidden_state=64, net_arch=[256,256])`；`pretrained=False`；优化器为 Adam，lr=1.5e-4，梯度裁剪上限 10。
- `prepare_observation`：速度、加速度分别按 `vel_max`、`acc_max` 归一化，再用 `lattice_Rbp_list[::-1]` 旋转到各原语坐标系，输出 `[B,9,3,5]`；顺序与上游 `inference()` 循环一致（tests/test_policy_runtime.py 有逐元素对照）。
- `decode_all`：复用上游可微解码 `pred_to_endstate(prediction[:,:,i], 14-i)`，只做批量拼接，不重新实现几何。
- `MapBank(dataset_root, shards, cfg)`：逐 shard 读取 `map.json` 与 `sdf.npy`（mmap），要求 `backend == "original_main_bucket"`；`CostConfig.duration = 2*radio_range/vel_max`（当前 1.333 s）。
- `MapBank.evaluate`：
  - 起点 `[p, R@v, R@a]`；目标 `pos + R@(10*obs[6:9])`（`goal_length=10`）。
  - 候选先由 body 系旋到 world 系再查询 SDF；`dJ/dend_body = Rᵀ · dJ/dend_world`；返回前应用上游单边裁剪 `np.minimum(grad, 1.0)`。
- `GuidanceCost`：forward 在 CPU NumPy 计算代价与梯度，backward 用保存的梯度乘上游梯度——代价本身不可导，但 ends 获得明确指导梯度。
- `losses`：`score = prediction[:,9].reshape(B,15)`；`score_loss = smooth_l1(score, cost.detach())`；两路共享骨干参数，评分支路不经过 `ends`。

输入：深度 `[B,1,96,160]`（0–20 m 归一化）、`obs[9]`、map id；输出：`total/trajectory/score` 三个标量。依赖 torch、numpy、scipy、pyyaml 与本地 external 源码。

## main_cost.py

- `CostConfig` 默认值＝上游 `traj_opt.yaml`：`smooth=4e-5`、`collision=1e-3`、`goal=2e-4`、`length=0`、`alpha=10`、`d0=1.2`、`radius=0.6`、`offset=1e-3`。
- `cost_and_gradient(start[B,3,3], end[B,3,3], goal[B,3], sdf, lower, upper, config)` 返回 `J[B]`、`dJ/dend[B,3,3]`（世界系）与分项明细：
  - 平滑项为五次多项式 jerk 积分 `boundary @ R @ boundary`；
  - 碰撞项取 30 个采样点，`dt = duration/30`，形如 `alpha*exp(-(d-d0)/r)`；
  - 目标项 `|p_end - goal|²`；长度项 `exp(-||Δp_xy||²/100)`（当前权重 0，保留）。
- `boundary_distance/boundary_gradient`：越界时用边界距离替换 SDF 值；梯度采用上游 stencil `(10*central+3*positive+3*negative)/(32*Δ)`，保留其特定 cross-axis 组合。
- 保留上游精度语义：`getPositionFromCoeff` 的 float32 中间量（`position.astype(np.float32)`）；模块 docstring 注明"完整 C++ oracle 验证在正式训练前必须完成"。
- `upstream_network_gradient`：`np.minimum(grad, 1.0)`，注释明确"不是对称 [-1,1] 裁剪"。

## quintic.py

- 状态约定：每行一个空间轴，列 `[p,v,a]`；`matrices(duration)` 返回 `(L, H, R=LᵀHL)`，与固定版 `qp_generator.cpp` 对齐。
- 注释陷阱：上游注释写 snap，但代码实际是三阶导数的 jerk 积分；本模块按上游代码实现并在 docstring 中说明。
- `Quintic` 提供 `evaluate(times, derivative)`、`jerk_integral()`、`end_gradient()`，对输入做形状与有限性校验。

## maps.py

- `surface_points(scene, spacing)`：地面网格＋树柱侧面/顶底盖＋灌木盒面；`write_ply` 写二进制 PLY。
- `pointcloud_esdf(points, resolution=0.2)`：SciPy EDT 生成 `outside - inside` 距离场；体素索引用上游"向零截断"约定（负坐标与上边界行为保留）。
- `VoxelSDF.query`：返回最近格点值、中心/单边差分梯度与 valid 掩码；越界返回 `inf` 与零梯度；默认 `index_mode="upstream_truncate"`，`floor` 仅供测试对照。
- 已知语义：占用来自表面采样，障碍内部不填充；碰撞真值以场景实体为准。

## forest.py

- `generate(seed, density=1/30, extent=80)`：种子可复现的程序化树（64 边柱）与灌木，`provenance` 字段注明"非 Flightmare 资产"。
- `ray_depth`：返回光学-Z 光线参数（非欧氏距离），支持多边柱精确求交、圆柱回退与盒体平行光线。
- `author_scene`：生成带 Collision API 的 USD 网格/盒体，供 Isaac 采集链使用（见 [implement/04_isaac_sim](../04_isaac_sim/README.md)）。

## dataset.py

- `ForestDataset(root, split, cfg, seed)`：校验 `dataset.json status=complete`；`depth_m.npy` 以 mmap 读取；深度裁剪到 20 m 后线性缩放到 96×160（与 `paper_aligned.json` 的 depth 段一致）。
- 训练集按 `(seed, epoch, shard, index)` 生成确定性增强（速度/加速度分布来自 `traj_opt.yaml`）；验证集固定 `epoch=0` 冻结；返回 `obs=[v,a,goal]` float32 与 map id。
- `stack_batch` 供训练/验证循环拼批。

## 数值对齐证据（C++ 参考实现）

由容器内 `scripts/ros2/check_*`（见 [implement/03_ros2_runtime](../03_ros2_runtime/README.md)）产生：

| 证据 | 状态 | 范围 |
|---|---|---|
| [artifacts/environment/quintic_cpp_parity.json](../../artifacts/environment/quintic_cpp_parity.json) | passed | L/H/R 矩阵，4 组 duration |
| [artifacts/environment/cost_cpp_parity.json](../../artifacts/environment/cost_cpp_parity.json) | passed（32 例，误差 ~1e-15） | 代价与雅可比，解析平面 SDF 桩 |
| [artifacts/environment/sdf_cpp_parity.json](../../artifacts/environment/sdf_cpp_parity.json) | difference_found（random_1 栅格 4 个体素 >1e-6，最大 0.0668） | 完整小网格 EDT 函数体对比 |
| [artifacts/environment/voxel_cpp_parity.json](../../artifacts/environment/voxel_cpp_parity.json) | passed（204 次查询） | 网格索引与存储值 |

## 测试

```powershell
Set-Location '<项目根目录>'
python -m pytest -q tests/test_quintic.py tests/test_main_cost.py tests/test_maps.py tests/test_forest.py tests/test_policy_runtime.py
```

`pytest.ini` 已设置 `pythonpath=src scripts`；若默认临时目录不可写，追加 `--basetemp=.pytest_basetemp/<name>`（仓库已有该目录约定）。test_policy_runtime 需要 torch 环境，其关键断言：`build_policy` 初始化期间不允许读取任何 checkpoint（用 `patch('torch.load')` 强制失败）。

## 已知限制

- 论文文字与可运行 main 的差异按 main 行为实现：正代价 + ReLU 评分 + `argmin` 选择、无候选筛选（`unselect=0`）；差异清单见 [report/02_method](../../report/02_method/README.md) 与 [report/02_method/03_原论文与源码差异审计.md)。
- 指导梯度是"数值指导梯度"（离散格点＋差分＋单边裁剪），不是解析真导数；SDF 由外部提供（`sdf.npy`），本目录不含其构建。
- `forest.py` 是程序化 Isaac 等价场景，不是原 Flightmare 资产；结论按"等效条件实验"陈述。
- 本目录不含 ROS2 运行时、在线规划与 Isaac 采集，分别在 implement/03 与 implement/04 登记。

## 相关入口

- 论文、源码版本与对齐规则：[plan/01_paper_protocol](../../plan/01_paper_protocol/README.md)
- 论文到代码的逐项对照：[report/02_method](../../report/02_method/README.md)
- 训练如何消费这些模块：[implement/02_training_pipeline](../02_training_pipeline/README.md)

