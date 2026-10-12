# 论文方法与本地实现逐项对照

更新：2026-10-12 ｜ 论文快照：[YOPO_author_version.txt](../../artifacts/paper_sources/YOPO_author_version.txt)（同名 PDF 在同目录）｜ 事实来源：[逐项对照报告](02_YOPO笔记与本地复现逐项对照_2026-10-08.md)、[原论文与源码差异审计](03_原论文与源码差异审计.md)

一句话结论：本地复现实现了论文的核心方法（视觉与状态输入、空间原语、多候选终端状态、外部代价梯度、共享网络联合学习、在线滚动规划），但不是论文叙述与实验设置的逐项等价复现。差异集中在评分符号、候选筛选、损失权重、数值梯度、轨迹时域、执行频率和实验平台，索引见[模块总图](../00_index/01_module_map.md) §3。

## 1. 论文方法与本地数据流

论文 II 的一阶段规划器在本地拆成“训练时”和“在线时”两条数据流。

训练（Guidance Learning）：

```text
depth[1x96x160] + state[9]
  -> 共享骨干网络 + 卷积头，一次 forward 输出 Bx10x3x5
  -> decode_all -> 15 个候选终端状态 Bx15x9
  -> 五次多项式 + 特权 ESDF 地图 -> 每个候选的代价 J（MapBank 查询）
  -> 两条损失：mean(J) 与 SmoothL1(score, J.detach())
  -> total = trajectory + 10 x score_loss -> backward（外部指导梯度接回网络）
```

在线（ROS2 闭环）：

```text
depth + state -> 同一网络 -> 15 个预测代价 -> argmin 选择 1 个候选
  -> 只解码所选端点 -> 五次多项式 -> 时间检查 -> 标准轨迹消息 -> 控制器 -> PhysX
```

实现分两层：固定上游源码 [external/audit_sources/main](../../external/audit_sources/main)（官方 main 数值语义的网络与解码）+ 本地训练封装 [src/yopo_repro](../../src/yopo_repro)（训练循环、代价、地图、多项式）。

## 2. 论文 II-A 对照：网络、原语与梯度

| 论文概念 | 本地实现 | 代码位置 | 判断 |
|---|---|---|---|
| 深度 + 状态输入 | 深度预处理为 B×1×96×160；9 维状态（速度、加速度、目标方向）变换到各原语坐标系 | [src/yopo_repro/policy.py](../../src/yopo_repro/policy.py) | 一致 |
| 空间原语覆盖搜索空间 | 固定方向与范围；tanh 后的输出决定角度修正、半径、终端速度与加速度 | [yopo_policy.py](../../external/audit_sources/main/flightpolicy/yopo/yopo_policy.py)、[primitive_utils.py](../../external/audit_sources/main/flightpolicy/yopo/primitive_utils.py) | 一致 |
| 一次前向并行预测多候选 | 共享骨干 + 卷积预测头，一次 forward 得 B×10×3×5（=15 候选 ×（9 参数 + 1 评分），解码后 B×15×9） | 同上 | 一致，注意布局（10×3×5 不是 15×9） |
| 轨迹与评分两类输出 | 单骨干共享参数；state_backbone 为空 Sequential，状态主要走几何处理；两个支路通过共享参数间接耦合 | yopo_policy.py | 一致（结构有简化） |
| ESDF 提供数值梯度 | MapBank 将候选变换到世界系查询地图；GuidanceCost 保存外部梯度并在 backward 接回 | [src/yopo_repro/main_cost.py](../../src/yopo_repro/main_cost.py)、[maps.py](../../src/yopo_repro/maps.py) | 一致，但为格点 + 差分梯度（D4） |
| 训练时查看全部候选 | `decode_all` 解出 B×15×9 终端状态参与代价计算 | src/yopo_repro/policy.py | 一致；在线只解码所选（D7） |

## 3. 论文 II-B 对照：两条损失与训练策略

真实训练代码等价于（取自[逐项对照报告](02_YOPO笔记与本地复现逐项对照_2026-10-08.md) §3 的核对结果）：

```python
prediction = policy(depth, primitive_frame_state)
ends = decode_all(policy, prediction)
cost = GuidanceCost.apply(ends, pos, rotation, obs, map_id, bank)
score = prediction[:, 9].reshape(B, 15)
trajectory = cost.mean()
score_loss = smooth_l1_loss(score, cost.detach())
total = trajectory + 10 * score_loss
total.backward()
clip_grad_norm_(policy.parameters(), 10)
optimizer.step()
```

要点：

- 路径1（轨迹）：网络轨迹参数 → 解码端点 → 五次多项式 → 计算 J 与地图指导梯度 → 自定义 backward → 网络。MapBank 内部暂时 detach 到 CPU NumPy 计算，但 GuidanceCost.backward 明确把保存的梯度接回 ends，学习未断。
- 路径2（评分）：网络评分 → SmoothL1(score, J.detach()) → 网络；评分分支不把已解码轨迹作为输入，也不会通过 J 再直接优化 ends。两路只通过共享骨干间接耦合。
- 平均尺度：N=B×15；轨迹损失对每个 cost 元素的上游梯度为 1/N（正式 batch 16 时 1/240）。评分项对每个评分的梯度为 clamp(score−J,−1,1)/N，合入总损失再乘 10。
- 权重与裁剪：`trajectory + 10 × score_loss`（不是无权重求和）；地图梯度另有 `minimum(g,1)` 单边裁剪，参数整体做范数裁剪（D3、D4）。
- 候选筛选：本地 `unselect=0`，损失没有筛选掩码，全部 15 个候选都贡献轨迹损失，与论文的筛选描述不同（D2）。
- 数据：Isaac 自生成数据，每轮重采速度/加速度/目标方向做状态增强，验证/测试集固定；训练器不加载专家缓存，专家仅用于离线比较（D9、D10）。

## 4. 论文 III 对照：实验部分

| 论文位置 | 论文内容 | 本地对应 | 证据与报告 |
|---|---|---|---|
| III-A Table I | 专家 vs 网络的代价与时延 | 重建专家求解器（scaled_gd50、MMA）在独立 10,000 样本测试集比较三种子与随机初始化 | [table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md)、[network_comparison_trained_seed0.json](../../artifacts/expert/network_comparison_trained_seed0.json)、[专家50步比较](../03_training/03_专家50步比较.md) |
| III-B Table II / Fig.7 | 与 TopoTraj、MPPI、Agile Autonomy 的仿真对比 | 正式矩阵覆盖三种子 YOPO 权重 + TopoTraj + Agile，已完成 1500/1800；MPPI 300 槽未执行 | [summary.json](../../artifacts/benchmark_summary/summary.json)、[figure_7](../../artifacts/paper_figures/figure_7_success_vs_speed.png)、[权重批量对照实验](../04_evaluation/02_权重批量对照实验.md)、[基准运行配置冻结](../04_evaluation/04_基准运行配置冻结.md) |
| III-C Real-world | 实机平台实验 | 未复现实机；本地以 Isaac + ROS2 仿真闭环替代 | [ROS2基线迁移记录](../04_evaluation/06_ROS2基线迁移记录.md)、差异 D11 |

## 5. 在线推理与执行（论文 II-A 推理阶段）

- 选择与解码：[main_planner.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py) 先按预测代价 argmin 选候选，再只解码所选终端状态，随后构造五次多项式。
- 轨迹时域：训练 T=2×4/6≈1.333 s；在线按目标速度更新 lattice，T=8/v，4 m/s 时为 2 s（D5）。
- 频率：相机名义 15 Hz，控制 100 Hz，物理 500 Hz；轨迹按 21 个带时间点发布，异步接受率不能等同名义规划频率（D6）。
- 重规划起点：有效旧轨迹存在时从旧参考在当前时刻的 p/v/a 续接，否则用观测 p/v 与零初始加速度（D8）。
- 闭环为仿真：里程计来自仿真状态，本地没有实机链路（D11）；分工与论文一致——网络输出参考轨迹，执行侧控制器与电机跟随。

## 6. 差异清单与影响

| # | 差异 | 影响 |
|---|---|---|
| D1 | 正代价 J、argmin（论文为负评分 −J、argmax） | 符号不能混用；把在线选择改回 argmax 会得到错误结果 |
| D2 | 全部 15 候选参与轨迹损失（论文为筛选后候选） | 训练监督范围更大，属于实质训练差异 |
| D3 | `mean(J) + 10 × SmoothL1`（论文为两条梯度相加） | 两路相对权重不同 |
| D4 | 格点 + 差分梯度、`minimum(g,1)` 裁剪（论文为精确导数） | 指导梯度是数值近似的受限版本 |
| D5 | 训练 1.333 s、在线 T=8/v（论文/笔记为固定 2 s） | 时空尺度不同 |
| D6 | 控制 100 Hz、物理 500 Hz（笔记为 50 Hz 控制） | 不能按 15/50 Hz 解读日志 |
| D7 | 在线只解码所选端点（论文流程解码全部） | 训练代码 decode_all 仅用于训练 |
| D8 | 从旧参考续接重规划（论文按测得状态） | 执行语义不同但轨迹连续 |
| D9 | Isaac 自生成数据与场景（论文 Flightmare/论文设备） | 结论按“等效条件实验”表述 |
| D10 | 专家不参与训练（论文叙述需要专家演示） | 训练是纯自监督 + 地图指导 |
| D11 | 无实机实验（论文 III-C） | 飞行证据全部来自仿真闭环 |

## 7. 证据与复核方法

- 计算图检查：[training_graph_trace.json](../../artifacts/note_alignment_20261008/training_graph_trace.json)——用 seed0 审计权重和两条独立测试样本在 CPU 上验证：评分损失不直接经过 ends、轨迹损失不经过 score、mean(J) 上游梯度 1/30（B=2）、两路梯度均非零、共享首层 `g_traj + 10·g_score` 的最大绝对误差 2.3e-09、模型文件未变。
- 权重审计：`checkpoints/formal_main_v1_seed{0,1,2}/training_audit.json`；最佳权重哈希与训练审计一致。
- 复核入口：[执行手册](../00_index/02_执行手册.md)；相关脚本 `scripts/audit_training_run.py`、`scripts/check_training_integrity.py`、`scripts/check_model_selection.py`。
- 边界：探针环境（torch 2.11.0／NumPy 2.3.1）与正式训练容器不同，只验证结构与梯度路径，不是历史数值重放或性能评测；探针只用两条样本，不能扩展成全库保证（[逐项对照报告](02_YOPO笔记与本地复现逐项对照_2026-10-08.md) §4、§8）。

## 8. 阅读提示

建议在笔记中保留三种标记，避免把推论当成可运行事实：

1. 论文原文——负评分、argmax、固定 2 s 等叙述；
2. 本地 main 实现——正代价、argmin、T=8/v、全候选训练等实际行为；
3. 教学示例／个人推论——解释用，不直接对应任何一边的实现。

每个差异背后的完整代码行号与核对过程见[逐项对照报告](02_YOPO笔记与本地复现逐项对照_2026-10-08.md)；实验缺口与状态见[模块总图](../00_index/01_module_map.md) §4 与[复现状态总览](../01_status/02_复现状态总览.md)。
