# YOPO 贡献与实施规则

## 目录职责

- plan：计划、协议、决策、变更。
- implement：代码实施和验证入口；实际运行源码保留根目录兼容路径。
- report：对用户可读的当前报告、图表、视频和迁移说明。

## 提交前检查

```powershell
python scripts/audit_command_evidence.py --fail-on-missing
python -m py_compile scripts/*.py
python scripts/make_status_overview.py
```

提交说明应写出变更目的、影响模块、验证命令和未闭项。不要提交凭据、私有路径或未经清理的临时运行目录。修改固定协议、验收规则或审计文件时必须先建立 plan/90_decisions/DEC-YYYYMMDD-NN.md。

