# CEG

`CEG` 是从 `CEG-WM` 清理式重构出的干净研究代码库。当前仓库只抽取方法机制、实验协议、baseline 适配、产物重建和发布包边界, 不迁入 `CEG-WM` 中嵌入代码内部的历史门禁、冻结治理、runtime whitelist 或 policy path 逻辑。

## 方法边界

CEG 方法严格遵循 `D:/Code/CEG-WM/doc/方法机制.md` 中的双链与事件约束定义:

```text
content_chain        负责 watermark 主证据
geometry_chain       负责参考系恢复, 不直接产生 formal positive
recover_then_content 使用同一内容阈值执行恢复后重判
attestation          只约束 final-level 归因一致性
payload_probe        只作为诊断字段, 不进入 formal decision
```

正式判定语义为:

```text
positive_by_content = content_margin_raw >= 0
rescue_eligible = 边界失败 AND geometry_reliable AND content_fail_reason 可救回
positive_by_geo_rescue = rescue_eligible AND content_margin_aligned >= 0
evidence_decision = positive_by_content OR positive_by_geo_rescue
final_decision = evidence_decision AND attestation_pass
```

## 核心目录

```text
main/methods/ceg/              CEG 核心方法与机制消融
main/methods/baselines.py      外部 baseline 注册表
main/methods/baseline_adapters.py  baseline observation 到统一 record 的适配
main/protocol/                 事件协议与统一运行时
main/analysis/                 结果聚合与 PW02 / PW04 等价产物重建
experiments/                   baseline 文件/命令适配与 paper protocol runner
main/cli/run_paper_protocol.py 轻量 CLI 入口
configs/                       active profile 与方法契约
scripts/                       发布包与复现辅助命令
```

## Active profiles

当前 active profile 包括:

```text
paper_main_probe
paper_main_pilot
paper_main_full
paper_mechanism_geo_search
paper_mechanism_quickcheck
paper_mechanism_pilot
```

`paper_main` 只允许:

```text
positive_source
clean_negative
```

`paper_mechanism` 额外支持机制消融:

```text
Full
Content-only
Recover-then-Content
No-rescue
No-attestation
```

## 外部 baseline

已登记的外部对比方法包括:

```text
Tree-Ring
gaussian_shading / Gaussian Shading
shallow_diffuse / Shallow Diffuse
stable_signature_dee / Stable Signature DEE
```

外部 baseline 可以通过两种方式进入统一流程:

1. 在事件 JSON 的 `payload.baseline_observations` 中直接提供 observation。
2. 使用 `experiments/baseline_file_adapter.py` 或 `experiments/baseline_command_adapter.py` 从 JSON / JSONL / CSV / 外部命令输出读取 observation。

baseline observation 最小字段为:

```text
event_id
baseline_id
score
threshold
```

## 运行轻量协议

示例命令:

```bash
python -m main.cli.run_paper_protocol \
  --events path/to/events.json \
  --thresholds path/to/thresholds.json \
  --profile paper_main_probe \
  --out path/to/local_run
```

该命令会生成:

```text
event_records.json
protocol_summary.json
artifacts/artifact_manifest.json
artifacts/formal_final_decision_metrics.json
artifacts/content_score_distribution_audit.json
artifacts/content_threshold_degeneracy_report.json
artifacts/formal_main_table.csv
artifacts/rescue_metrics_summary.csv
artifacts/baseline_comparison_table.csv
artifacts/method_group_comparison_table.csv
```

## 发布包

构建最小方法包:

```bash
python scripts/build_release_package.py \
  --profile minimal_method_package \
  --root . \
  --output path/to/minimal_method_package
```

构建论文产物重建包:

```bash
python scripts/build_release_package.py \
  --profile paper_artifact_rebuild_package \
  --root . \
  --output path/to/paper_artifact_rebuild_package
```

`minimal_method_package` 默认包含:

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
.codex/
tools/
tests/
experiments/
scripts/
paper_workflow/
audit_reports/
outputs/
```

## 必需检查

```bash
pytest -q
python tools/harness/run_all_audits.py
```

当前测试覆盖:

```text
CEG formal decision
CEG 机制消融
外部 baseline 注册表
baseline 文件适配
baseline 命令适配
protocol runner
PW02 / PW04 等价产物重建
minimal_method_package 独立导入
paper_artifact_rebuild_package 独立 CLI 运行
```
