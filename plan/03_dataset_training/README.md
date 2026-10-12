# 03 数据与训练计划

## 数据版本

数据集 isaac_full_v1：20张训练地图/100,000样本、4张验证地图/10,000样本、4张测试地图/10,000样本。深度、位姿、地图和SDF均有清单与哈希。

## 正式训练

main网络、ResNet18、随机初始化、Adam、学习率 1.5e-4、batch 16、50轮、seed 0/1/2。每轮验证，保存epoch checkpoint、优化器、随机状态和验证集选择的 best_policy.pth。

## 微调

审计后的seed0在新地图闭环采集访问观测，构建 isaac_dagger_v1，再独立微调10轮。它不是第四个正式seed，不能覆盖基础run。

训练代码见 implement/02_training_pipeline/README.md。
