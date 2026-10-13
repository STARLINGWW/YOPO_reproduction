# smoke_v1 迁移验证子集（随库发布）

`smoke_v1` 的完整采集目录约 480MB；随库发布的只有一个裁剪子集：`dataset.json`、`validation.json`，以及 4 个 shard 各 5 个文件（`manifest.json`、`map.json`、`depth_m.npy`、`poses.npz`、`sdf.npy`——`train_scratch.py validate_data()` 所需的全部文件）。`collect_*.log`、`occupancy.u8`、`sdf.f32`、`pointcloud.ply`、`scene.json`、预览图等派生文件不随库发布。

用途：在干净 clone 中执行迁移 smoke（见 `MIGRATION_UBUNTU22.md`）：

```bash
docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run clean_clone_smoke --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run clean_clone_smoke --seed 0 --epochs 1 --batch-size 16 --resume
```

随库文件 SHA256（2026-10-13，Git LFS 保存原始字节）：

```
64d3ca502fe684e8d90e172f9cc9e382f8208db5f7eb85a1ae418a5d87a68d00  dataset.json
dbcc8b134e3f37d5f95e821bb8a9a6ffd7ee9b437fedc029a46e4b74d84291be  validation.json
588bf7d5a8c5d32af3de294959c8203a32d5b6959408b9e61777bd1993f908a4  shards/000/manifest.json
1498dfade4f3d482addb95fb60c3af81ae055f8185137989e7cbee2435338d08  shards/000/map.json
596d5d0a9881496a945da910f3854a6389fb82343bd7aefe1567244bc00537bc  shards/000/depth_m.npy
d55432c44c0d7729eaa2b651927c6a00f96179690d90ffe3ea17b5f06b483ae5  shards/000/poses.npz
728ea5e2d974816dd85d92b65003e23ae9a74f175b63f0102853fd7ca7575390  shards/000/sdf.npy
84d6e8705dbebdaca785d7c993e6f34b8b0a704f422b6817251f210b15ec87e5  shards/001/manifest.json
0580f1daacd7a8fc86695dd973081da7079e9bf8225a0ff3db91d79fc987fa32  shards/001/map.json
55be579b364d3407c9358b545f77af99e6663d1ce4411ee1a4986ca33a3ba904  shards/001/depth_m.npy
17a0f95cb7270da7726fffd561831f531ed159c6b89f0624870c1ab8993bb044  shards/001/poses.npz
a60a3398c2aa98efd357e3f186522107b048ca173116136076913811f84582e1  shards/001/sdf.npy
81e9c33887443f3ef7130e21a0c53b8829765a6a65a3bbd0d773d7c4c7734a1c  shards/002/manifest.json
5f372c35674d1854059751f497240602513bf72b430f5af4e3fbaed8be16c778  shards/002/map.json
2f2d7e82efcea3744fedd84f128f4ca211a6d1f6fba3a67b7ac5fd79da3490f1  shards/002/depth_m.npy
b205d4fc95dbe61f5173cea8c1a847ce246ce70bfc378d58743a967cd678463c  shards/002/poses.npz
22ec395740e01381e1010aee9363e281b101a2afbd69e06121e73497cf832e75  shards/002/sdf.npy
56cfaaa7685eec7a6b3dcfcc1d22f2d2f844a28563cc201d5e1b7f4021c352ab  shards/003/manifest.json
dc875d57ec3aa748ef3571d78b9b63e8345cc26c245de126700ae3bd0f6b8460  shards/003/map.json
d5b8094f82722d530c40d107e3f6e7aea5db0edaef349306e48a859e0922952e  shards/003/depth_m.npy
3d610e06b425c0e40ca6b03d085593eccf12e32d194670ac1076e0a4d4696e55  shards/003/poses.npz
a4bb7d2fa16a53df2f0ab474ada7da97065940f0470f87c489bdd7585c8eb3b3  shards/003/sdf.npy
```

`dataset.json`/`validation.json` 本身与 shard 内清单互相记录哈希；以上数值可由 `Get-FileHash`（Windows）或 `sha256sum`（Linux）复算。
