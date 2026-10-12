# implement/workspace：代码工作区视图

代码的**真实文件**位于项目根目录（`src/`、`scripts/`、`configs/`、`docker/`、`ros2_ws/`、`tests/`、`external/`、`benchmarks/`、`vendor/`、`assets/`）。运行兼容、Docker 挂载（`.:/workspace`）、脚本的相对路径解析和冻结证据里的文件哈希都依赖这个相对位置，因此代码不物理搬进 implement，否则训练、ROS2 闭环和已有审计链都会被破坏（实测：Docker 挂载不会穿越 junction）。

本目录是它们的工作区视图：本地用 NTFS junction、Linux/Ubuntu 用符号链接，把根目录的代码区映射进来，方便在 implement 里一站式阅读和接管。

## 生成视图

- Windows（PowerShell，无需管理员）：`./bootstrap_links.ps1`
- Ubuntu 22.04 / Linux：`bash bootstrap_links.sh`

## 视图内容

| 链接 | 指向 | 内容 |
|---|---|---|
| `src` | `../../src` | 算法库：yopo_repro、yopo_sim、yopo_expert、agile_runtime、yopo_eval、yopo_dagger |
| `scripts` | `../../scripts` | 全部运行入口（数据、训练、审计、基准、渲染、PS1 流水线） |
| `configs` | `../../configs` | 协议与模型配置 |
| `docker` | `../../docker` | 镜像定义（jammy / CUDA 12.8 / ROS2 Humble） |
| `ros2_ws` | `../../ros2_ws` | ROS2 工作区（源码在 `ros2_ws/src`，构建产物不入库） |
| `tests` | `../../tests` | 单元与契约测试 |
| `external` | `../../external` | 固定上游源码（audit_sources） |
| `benchmarks` | `../../benchmarks` | 冻结协议与准入记录 |
| `vendor` | `../../vendor` | 运行时依赖快照 |
| `assets` | `../../assets` | Isaac 机体 USD 资产 |

## 接管约定

1. 所有命令仍从**项目根目录**执行（例如 `python scripts/train_scratch.py ...`、`docker compose --profile training run ...`）。
2. 改动代码的真实路径是根目录文件；本目录的链接只是视图，不要在这里新建文件。
3. 每个模块的代码地图见 `implement/00_workspace_map` … `implement/07_visualization`。
4. 新增文件请遵守 [implement/99_workspace_rules](../99_workspace_rules/README.md)。
