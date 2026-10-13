# 06 GitHub 与 Ubuntu 迁移计划

## 仓库分层

GitHub主仓库保存源码、配置、Docker、ROS2源码、计划和Markdown报告。大数据、检查点、视频和原始飞行输出按发布清单选择性上传，使用 Git LFS 或外部对象存储，不能直接把全部运行目录提交到普通Git。

## 首次建仓

在 YOPO_reproduction 目录执行：

```powershell
git init
git branch -M main
git add .gitignore .gitattributes README.md AGENTS.md CONTRIBUTING.md LICENSE plan implement report reports src scripts configs docker ros2_ws/src tests compose.yaml pytest.ini
git commit -m "docs: establish plan implement report project structure"
git remote add origin <YOUR_PRIVATE_GITHUB_URL>
git push -u origin main
```

远端已有内容时先 pull --rebase，解决冲突后再推送。不要把远端地址或令牌写入项目文件。

## 大文件

```powershell
git lfs install
git lfs track "*.pth" "*.pt" "*.npy" "*.npz" "*.mp4" "*.pdf" "*.usda"
git add .gitattributes
git add checkpoints datasets artifacts/ros2_showcase artifacts/showcase
git commit -m "data: add selected reproducibility artifacts"
git push origin main
```

2026-10-13 更新：v2 发布替换旧 main（旧 main 先打 `archive/pre-yopo-only-20261013` tag）。主仓库发布三个正式 `best_policy.pth`、DAgger `best_policy.pth` 及其 manifest/审计文件与代表媒体（Git LFS）；完整 `isaac_full_v1`、中间 checkpoint 与 11GB 以上飞行输出走 Release/对象存储，并在 report/06_migration 写入 SHA256 获取说明。

## Ubuntu 22.04

1. clone主仓库。
2. 安装匹配NVIDIA驱动和NVIDIA Container Toolkit。
3. 构建或加载 train-cu128-jammy 镜像。
4. 下载数据和checkpoint归档并校验哈希。
5. 运行GPU/ROS2环境检查。
6. 运行smoke训练、停止、恢复。
7. 再运行正式训练或载入已有模型。
8. 需要闭环时单独安装和验证Isaac Sim。

训练入口必须使用容器Python，不能依赖Windows Isaac绝对路径。

