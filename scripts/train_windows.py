"""Native Windows launcher for the pinned upstream trainer.

Requires a real, validated YOPO dataset. No ROS, WSL or Docker dependency.
The upstream per-map validation split is retained, so held-out-map evaluation
must be performed separately. Outputs never overwrite the pretrained weights.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--save-interval", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.save_interval) < 1 or args.workers < 0:
        parser.error("epochs, batch size and save interval must be positive; workers must be nonnegative")
    dataset = args.dataset.resolve()
    if not dataset.is_dir() or not list(dataset.glob("pointcloud-*.ply")):
        parser.error("dataset must exist and contain pointcloud-N.ply")
    sys.path.insert(0, str(ROOT / "external/audit_sources/YOPO-Simple/YOPO"))
    for vendor_dir in (ROOT / "vendor/probe_deps", ROOT / "local_only/vendor/probe_deps"):
        if vendor_dir.is_dir():
            sys.path.insert(0, str(vendor_dir))
            break
    import torch
    from config.config import cfg
    from train_yopo import configure_random_seed
    from policy.yopo_trainer import YopoTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable in the selected Python environment")
    cfg["dataset_path"] = str(dataset)
    cfg["train"] = True
    configure_random_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    trainer = YopoTrainer(learning_rate=1.5e-4, batch_size=args.batch_size,
                          loss_weight=[1., 1.], tensorboard_path=str(args.output.resolve()),
                          checkpoint_path="", save_on_exit=True)
    # No worker processes have started yet. Set native-Windows worker count
    # before either loader is iterated; default 0 keeps the first run simple.
    trainer.train_dataloader.num_workers = args.workers
    trainer.val_dataloader.num_workers = args.workers
    if min(len(trainer.train_dataloader.dataset), len(trainer.val_dataloader.dataset)) < args.batch_size:
        raise ValueError("Training and validation must each contain at least one full batch")
    run_dir = Path(trainer.tensorboard_path)
    manifest = {"source_commit": "bd8a7f91953cfef9f1aa9a48d7ff0ab7bceee132",
                "platform": "native-windows", "python": sys.version,
                "torch": torch.__version__, "cuda": torch.version.cuda,
                "dataset": str(dataset), "epochs": args.epochs,
                "batch_size": args.batch_size, "workers": args.workers, "seed": args.seed,
                "learning_rate": 1.5e-4, "configuration": cfg._data,
                "validation": "upstream within-map split; not held-out-map generalization"}
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    trainer.train(epoch=args.epochs, save_interval=args.save_interval)
    trainer.save_model()
    # Save optimizer and RNG state as a final snapshot for a later resume tool.
    import random
    import numpy as np
    torch.save({"model": trainer.policy.state_dict(), "optimizer": trainer.optimizer.state_dict(),
                "epoch": args.epochs, "python_rng": random.getstate(),
                "numpy_rng": np.random.get_state(), "torch_rng": torch.get_rng_state(),
                "cuda_rng": torch.cuda.get_rng_state_all()}, run_dir / "training_snapshot.pth")
    trainer.tensorboard_log.close()
    print("Training outputs:", run_dir)


if __name__ == "__main__":
    main()
