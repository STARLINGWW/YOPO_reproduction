# YOPO 复现项目重构总计划

版本：v1.0
日期：2026-10-12
范围：项目结构、管理方法、代码实施区、报告展示区、GitHub和Ubuntu 22.04迁移

## 1. 重构目标

建立三个职责明确的工作层：

plan：计划与管理，负责范围、协议、决策、变更和验收。
implement：实施与验证，负责算法、训练、ROS2、Isaac、基线、测试和可视化程序。
report：交付与展示，负责当前状态、方法说明、实验总结、图表、图片、视频和迁移报告。

plan规定目标和验收条件，implement产生代码和原始证据，report读取真实产物并形成可读交付。三层之间用编号、相对链接、run name、manifest和SHA256关联。

本次不为了分类而移动现有运行代码。训练和仿真脚本依赖项目根目录，容器依赖 /workspace；保持根目录运行兼容是迁移安全的一部分。

## 2. 最终目录设计

plan/
  00_charter/                 章程、范围、完成定义
  01_paper_protocol/          论文、源码、协议和差异
  02_environment_ros2/        环境、消息、时钟和接口
  03_dataset_training/        数据、训练、恢复和checkpoint
  04_runtime_baselines/       YOPO、专家、基线和MPPI
  05_benchmark_acceptance/    矩阵、统计、证据和验收
  06_github_migration/        GitHub、LFS和Ubuntu迁移
  90_decisions/               用户裁决与方案选择
  99_change_log/               计划和管理变更

implement/
  00_workspace_map/           根目录运行代码地图
  01_core_algorithm/          网络、原语、代价和轨迹
  02_training_pipeline/       数据、训练和恢复入口
  03_ros2_runtime/            ROS2协议、规划器和时钟
  04_isaac_sim/               Isaac采集、飞行和回放
  05_baselines/               专家、TopoTraj、Agile和MPPI
  06_validation/              测试、准入和证据契约
  07_visualization/           渲染器、指标图和视频
  99_workspace_rules/         大模型实施规范和任务模板

report/
  00_index/                   报告阅读顺序
  01_status/                  当前状态和完成度
  02_method/                  论文到本地实现的对应
  03_training/                正式训练、专家、DAgger
  04_evaluation/              矩阵、权重、基线和验收
  05_visualization/           视频、图片、回放和指标
  06_migration/               GitHub和Ubuntu接续
  90_archive/                 历史阶段报告
  99_artifact_index/          产物、哈希和下载索引

根目录现有 src、scripts、configs、docker、ros2_ws、tests、external、datasets、checkpoints、artifacts、reports 保留为运行兼容层。三个新目录提供管理和阅读入口，不复制大型数据和视频。

## 3. plan 管理层

计划文件必须包含：目标、输入、设计、影响文件、禁止修改文件、执行命令、验证命令、产物路径、风险、回滚方式和完成条件。

计划编号：

- P-00 项目章程。
- P-01 论文、源码与协议。
- P-02 环境与ROS2。
- P-03 数据与训练。
- P-04 运行时与基线。
- P-05 基准与验收。
- P-06 GitHub与Ubuntu迁移。
- P-90 决策。
- P-99 变更日志。

每次大模型实施任务先建立任务记录，写清目标、影响模块、不允许修改的证据文件、执行命令、验证方法、结果和失败原因。重要决定写入 DEC-YYYYMMDD-NN.md。

## 4. implement 实施层

核心算法对应：

- src/yopo_repro/policy.py：网络、候选解码和训练损失。
- src/yopo_repro/main_cost.py：轨迹代价和指导梯度。
- src/yopo_repro/quintic.py：五次多项式。
- src/yopo_repro/maps.py：距离场。
- external/audit_sources/main：固定main源码。

训练对应：

- scripts/prepare_dataset.py。
- scripts/collect_isaac_shard.py。
- scripts/train_scratch.py。
- scripts/audit_training_run.py。
- scripts/train_dagger_finetune.py。
- datasets/。
- checkpoints/。

运行时对应：

- ros2_ws/src/yopo_runtime。
- scripts/run_ros2_navigation.py。
- scripts/run_navigation.py。
- src/yopo_sim。
- docker和compose.yaml。

验证对应：

- tests/。
- scripts/validate_dataset.py。
- scripts/validate_ros2_flight.py。
- scripts/evaluate_ros2_flight.py。
- scripts/final_acceptance_audit.py。
- scripts/audit_command_evidence.py。

可视化对应：

- scripts/render_ros2_flight.py。
- scripts/render_flight.py。
- scripts/demo_flight.ps1。
- artifacts/ros2_showcase、artifacts/showcase、artifacts/paper_figures。

implement目录只保存代码地图、接口契约和实施日志，不复制源码造成双份维护。

## 5. report 交付层

报告编号：

- R-00 报告索引。
- R-01 当前状态。
- R-02 方法与论文对应。
- R-03 正式训练和DAgger。
- R-04 基准、专家和权重对照。
- R-05 可视化展示。
- R-06 GitHub与Ubuntu迁移。
- R-90 历史阶段。
- R-99 产物索引。

每份报告必须回答：做了什么、为什么做、改了什么、使用什么数据和模型、怎样运行、结果和失败是什么、证据在哪里、怎样复核、有什么限制、下一步是什么。

报告必须区分真实运行、离线检查、合成测试、历史记录、计划和推断。展示报告必须关联metrics、render_manifest和权重SHA256。

## 6. 实施阶段

阶段0：冻结。生成文件树、受保护文件SHA256、训练审计、当前验收、数据和checkpoint大小快照，输出 refactor_日期/before.json。

阶段1：入口。建立plan、implement、report目录及README、编号和交叉链接，只新增文档和索引。

阶段2：代码地图。为每个核心模块写implement导航，说明入口、输入、输出、依赖、测试和已知限制。

阶段3：报告整理。把当前报告分成状态、方法、训练、评测、可视化、迁移六类；root reports保留兼容和历史来源。

阶段4：Git管理。创建.gitignore、.gitattributes、LICENSE、CONTRIBUTING和Ubuntu迁移说明。先提交源码和文档，再提交可选LFS和演示包。

阶段5：迁移验证。Ubuntu 22.04完成clone、NVIDIA容器工具检查、训练镜像、GPU和ROS2探针、smoke训练、停止恢复、正式数据哈希、模型载入和必要的Isaac闭环。

阶段6：验收。链接检查、Python语法、PowerShell解析、核心测试、smoke恢复、权重哈希、协议哈希、代表视频和迁移命令通过后，写R-06迁移报告。

## 7. GitHub策略

主仓库提交源码、配置、Docker、ROS2源码、测试、固定上游、plan、implement、report、README、AGENTS、LICENSE和小型演示包。

默认排除 ros2_ws/build、install、log、pytest缓存、ros2飞行全量输出、全部深度npy、全部epoch检查点、私密凭据和本机日志。

pth、pt、npy、npz、mp4、pdf、usda使用Git LFS或Release/对象存储。完整59 GB数据不放入普通Git。每个外部包记录下载地址、版本、大小和SHA256。

首次建仓：

1. 在YOPO_reproduction中 git init。
2. 创建main分支。
3. 添加源码、配置、Docker、ROS2源码、plan、implement、report和小型测试数据。
4. 提交结构基线。
5. 添加私有GitHub origin。
6. push main。
7. 再按manifest上传LFS和Release数据包。

## 8. 完成标准

结构：三个入口目录有README、编号和入口；核心代码有implement导航；当前成果有report索引；历史报告标明日期和范围。

运行：原有训练、审计和回放命令继续可运行；固定协议、runtime准入、审计权重SHA256不变；文档链接和命令语法通过。

迁移：Ubuntu可构建训练镜像；smoke训练和恢复通过；正式数据与checkpoint按manifest恢复；训练不依赖Windows绝对路径。

GitHub：clone后可以阅读和启动最小训练检查；大文件有获取流程；私密文件未提交；CI至少运行Python语法、核心测试和文档链接检查。

## 9. 回滚

所有重构前文档备份到 artifacts/refactor_日期/backups。代码和证据文件不移动。入口整理出问题时可删除新建的plan、implement、report，原根目录运行结构仍可用。物理迁移代码必须另立决定，先加统一根目录解析函数和兼容包装，再执行。

## 10. 推荐顺序

1. 创建三个目录和入口README。
2. 创建implement代码地图。
3. 创建report当前报告和产物索引。
4. 完善Git忽略、LFS和GitHub操作说明。
5. 冻结哈希并运行文档与语法检查。
6. 初始化Git并提交结构基线。
7. 配置私有GitHub远端。
8. 上传源码和小型演示包。
9. 上传完整数据归档并记录哈希。
10. Ubuntu smoke迁移。
11. Ubuntu正式训练或模型接续。
12. 根据迁移结果更新R-06。

