# 02 训练流水线

基础训练由scripts/prepare_dataset.py、scripts/train_scratch.py和scripts/audit_training_run.py组成；DAgger由scripts/run_dagger_collection.py、scripts/build_dagger_dataset.py、scripts/stage_aggregation_dataset.py和scripts/train_dagger_finetune.py组成。

正式权重位于checkpoints/formal_main_v1_seed0、seed1、seed2。DAgger权重不覆盖正式seed，不进入原1800矩阵。

