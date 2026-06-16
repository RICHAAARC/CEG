# Release Boundary

## 与 extraction profile 的关系

本文件说明发布边界原则, `docs/extraction_profiles.md` 定义可执行的抽离 profile。发布包不应默认等同于开发仓库。

## 发布包类型

### `minimal_method_package`

该包是最小论文方法代码附件, 只保留核心方法、核心协议和最小配置。

默认包含:

```text
main/core/
main/methods/
main/protocol/
configs/
README.md
pyproject.toml
```

默认排除:

```text
main/analysis/
main/cli/
experiments/
scripts/
paper_workflow/
.codex/
tools/harness/
tests/constraints/
audit_reports/
outputs/
```

### `paper_artifact_rebuild_package`

该包用于重建论文所需 tables、figures、reports 和 manifests。它可以包含 artifact builders 和轻量功能测试, 但不包含外层治理实现。

默认包含:

```text
main/
configs/
experiments/
scripts/
docs/中必要的复现和 schema 文档
tests/functional/
README.md
pyproject.toml
```

默认排除:

```text
.codex/
tools/harness/
audit_reports/
outputs/
tests/constraints/
tests/integration/
```

## 默认进入论文发布包

- `main/`
- `configs/`
- `scripts/` 中必要的复现脚本
- `docs/` 中的方法、复现、数据准备和模型准备文档
- `tests/` 中可公开的复现测试
- 必要的 `experiments/` paper protocol

## 默认不进入论文发布包

- `.codex/`
- `tools/harness/`
- `audit_reports/`
- `outputs/`
- 本地 Notebook 缓存
- 私有数据或本地绝对路径配置
- 未经治理的临时实验结果

## 说明

该边界适用于论文代码开源前的最小发布抽取。内部治理材料可以保留在开发仓库, 但发布包应优先服务审稿复现和读者理解。

## CEG 当前发布验证

当前仓库提供两个可执行发布入口:

```bash
python scripts/build_release_package.py --profile minimal_method_package --root . --output <dir>
python scripts/build_release_package.py --profile paper_artifact_rebuild_package --root . --output <dir>
```

发布验证要求:

1. `minimal_method_package` 必须能在抽取目录中独立导入 `main.methods.ceg` 并运行 `decide_ceg_event`。
2. `paper_artifact_rebuild_package` 必须能在抽取目录中运行 `python -m main.cli.run_paper_protocol` 并重建 `formal_main_table.csv`、`baseline_comparison_table.csv` 等产物。
3. 发布包不得包含 `.codex/`、`tools/`、`audit_reports/` 或 `outputs/`。
4. baseline 的第三方实现不进入核心方法包, 只通过 observation 文件或命令适配器接入。



## 实验覆盖率产物边界

`paper_artifact_rebuild_package` 可以包含 `experiments/experiment_coverage.py` 和 `scripts/validate_experiment_coverage.py`。它们属于结果审计层, 只消费 records 与实验矩阵, 不属于 CEG 核心判定算法, 因此不进入 `minimal_method_package`。
