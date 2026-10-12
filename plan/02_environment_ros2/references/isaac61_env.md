# Isaac Sim 6.1 专用 conda 环境（isaac61）

面向 **传统 SLAM + 强化学习** 算法开发的独立环境，与既有 `isaaclab-win`
（Isaac Sim 5.1）并列存在、互不影响。

| 项目 | 值 |
| --- | --- |
| conda 环境名 | `isaac61` |
| 路径 | `D:\_AAA_FILE_ALL\Anaconda_file\Anaconda_env\isaac61` |
| Python | 3.12.14（Isaac Sim 6.1 强制 `==3.12.*`） |
| Isaac Sim | 6.1.0.0（`isaacsim[all,extscache]`，Kit SDK 110.x 系列） |
| PyTorch | **2.11.0+cu128**（官方指定版本），torchvision 0.26.0+cu128，torchaudio 2.11.0 |
| CUDA 设备 | RTX 5070 Ti，`torch.cuda.is_available()=True`，架构列表含 **sm_120** |
| 数值库 | numpy 2.3.1、scipy 1.17.0（Isaac Sim 锁定版本） |
| 视觉 | opencv-python-headless-noffmpeg 4.14.0.94rc1（Isaac Sim 锁定，来自 pypi.nvidia.com） |
| MuJoCo | **3.11.0 + mujoco-warp 3.11.0 + mujoco-usd-converter**（Isaac Sim 依赖自带） |
| RL | gymnasium 1.3.0、stable-baselines3 2.9.0、rsl-rl-lib 5.5.1、skrl 2.1.0、tensorboard 2.21.0、hydra-core 1.3.6、omegaconf 2.3.1 |
| SLAM/几何 | open3d 0.19.0、evo 1.37.1、rerun-sdk 0.37.2、scikit-learn 1.9.1、pandas、h5py |
| 视频 | imageio + imageio-ffmpeg 0.6.0（自带 ffmpeg 7.1） |
| 环境体积 | ≈ 20.3 GB |

## 安装命令（可复现）

```powershell
# 1) 环境（官方 Anaconda 源在本机可达；清华/中科大镜像存在 SSL 握手失败）
conda create -y -n isaac61 python=3.12 --override-channels -c defaults

# 2) PyTorch：官方指定 torch==2.11.0 + cu128（download.pytorch.org 实测 5.9 MB/s）
python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128

# 3) Isaac Sim 6.1（必须带 NVIDIA 额外索引，否则 opencv 预发布轮子找不到）
python -m pip install "isaacsim[all,extscache]==6.1.0.0" --extra-index-url https://pypi.nvidia.com

# 4) 外围库（RL/SLAM/视频）
python -m pip install imageio-ffmpeg gymnasium stable-baselines3 tensorboard hydra-core omegaconf `
    pandas h5py tqdm scikit-learn evo rerun-sdk rsl-rl-lib skrl open3d

# 5) 把外围库拉高的版本降回 Isaac Sim 的锁定值
python -m pip install "click==8.1.7" "psutil==5.9.8" "ipython<9" "protobuf>=6.31.1,<8"
```

## 镜像与下载速度实测（本机）

| 源 | 结果 |
| --- | --- |
| 清华 PyPI / 清华 conda / 中科大 | **SSL 握手失败**（`UNEXPECTED_EOF_WHILE_READING`），不可用 |
| 阿里云 PyPI | 可用但慢（≈124 kB/s） |
| 阿里云 pytorch-wheels | 可用但很慢（≈86 kB/s） |
| **pypi.org（官方）** | **≈1.7 MB/s**，最终采用 |
| **download.pytorch.org** | **≈5.9 MB/s**，最终采用 |
| repo.anaconda.com | 可达（conda 建环境用它） |
| pypi.nvidia.com | 可达，且提供 Isaac Sim 锁定的 `opencv-python-headless-noffmpeg==4.14.0.94rc1` |

结论：这台机器上"国内镜像"反而不如官方源快，且清华/中科大的 TLS 不可用，因此最终选择
官方源 + NVIDIA 索引。

## 依赖冲突与取舍（重要）

1. **Isaac Sim 的锁定优先**：`isaacsim-kernel` 锁定 `click==8.1.7`、`psutil==5.9.8`、
   `numpy==2.3.1`；`isaacsim-core` 锁定 `torch==2.11.0`、`torchvision==0.26.0`、
   `torchaudio==2.11.0`。外围库若拉高这些版本会破坏平台，已全部降回。
2. **未安装 wandb**：新版 wandb 要求 `click>=8.2`（与 Isaac Sim 冲突），旧版 wandb 又
   强制 `protobuf<6`（与 tensorboard 冲突）。本环境保留 **tensorboard** 作为 RL 曲线工具；
   若必须用 wandb，建议另建环境或使用 `--no-deps` 并接受 protobuf 冲突。
3. **gtsam 无法用 pip 安装**（PyPI 无 Windows 轮子）：需要 conda-forge
   (`conda install -c conda-forge gtsam`) 或放到 WSL/Ubuntu 环境；本环境未安装。
4. **rerun-sdk 声明 `psutil>=7`**，但 Isaac Sim 要求 `psutil==5.9.8`。当前仅剩这一条
   `pip check` 警告；rerun 的基本日志写入可用，`spawn` 视图器的进程探测可能受影响。
4. `pip check` 除上述 rerun 条目外无其他冲突。

## 兼容性与渲染验证（本机实测）

| 测试 | 结果 |
| --- | --- |
| 官方兼容性检查器（`isaacsim.exp.compatibility_check.kit`） | **System checking result: PASSED**，`Driver version [supported]`（595.97 / D3D12） |
| 无头启动（`SimulationApp(headless=True, enable_cameras=True)`） | 成功，冷启动 ≈10–13 s |
| RTX 相机渲染（`isaacsim.sensors.camera`，640×480） | 预热后 **150 帧 / 3.3–3.6 s ≈ 42–45 fps**（高于 30 fps 实时播放门槛） |
| 视频导出 | `artifacts/videos/isaac61_render_test.mp4`，H.264，150 帧全部回读，4 个立方体与地面、阴影可见 |
| 对照：Isaac Sim 5.1 同路径 | `--enable_cameras` **稳定崩溃**（access violation，发生在 `create_new_stage` → `omni.kit.widget.viewport` 纹理），两次复现 |

结论：**在 RTX 5070 Ti + 驱动 595.97 上，Isaac Sim 6.1 的相机渲染与视频导出链路可用**，
而 5.1 的同路径不可用。

## 许可（EULA）

Isaac Sim 6.1 的 `isaacsim.kit.kit_app.check_eula()` 会在首次启动时要求接受 NVIDIA
Omniverse 许可，接受记录写入 `<env>\Lib\site-packages\isaacsim\kit\EULA_ACCEPTED`。
既有 5.1 环境中该文件已存在（内容 `yes`），说明本机此前已接受同一份许可；本次测试
通过进程内环境变量 `OMNI_KIT_ACCEPT_EULA=YES` 非交互接受，**未写入新的接受文件**。

## 与 Isaac Lab 的关系

Isaac Lab 官方发布的最新版为 **3.0.0-beta2.patch1**，其发布说明写明面向
**Isaac Sim 6.0.1**；Isaac Lab `main` 分支的 `environment.yml` 仍为 Python 3.11
（对应 5.x 线）。因此：

* 若要用 **Isaac Lab**，最稳的组合是 `Isaac Sim 6.0.1 + Isaac Lab 3.0.0-beta2.patch1`；
* 若坚持 **Isaac Sim 6.1**，需要 Isaac Lab 的 `main`/更新分支，并自行承担未发布版本的
  兼容风险；本环境目前**只装了 Isaac Sim 6.1 独立 API**（渲染与视频已验证），尚未装
  Isaac Lab。

## 现有其他环境的定位（避免混用）

| 环境 | 用途 |
| --- | --- |
| `isaac61`（新） | Isaac Sim 6.1 + RL/SLAM + MuJoCo，主开发环境 |
| `isaaclab-win` | Isaac Sim 5.1 + Isaac Lab 2.3.2（相机路径崩溃，仅物理可用） |
| `pytorch_5070ti` | 本项目 01/04/05/06/07 的纯算法与仿真（NumPy/SciPy/PyTorch） |
