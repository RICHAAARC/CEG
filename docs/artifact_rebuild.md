# Artifact Rebuild Governance

正式 artifacts 必须满足：

1. records 是事实来源。
2. tables 由 records 或中间 governed tables 重建。
3. figures 由 records 或 tables 重建。
4. reports 由 records、tables、figures 和 manifests 生成。
5. manifests 记录输入、输出、代码版本、配置摘要和重建命令。
6. claims 只能引用 governed artifacts。

## 与核心方法的边界

Artifact rebuild 属于论文产物生成层, 不属于最小核心方法层。  
`main/analysis/` 可以依赖 `main/core/`、`main/methods/` 和 `main/protocol/`, 但 `main/core/`、`main/methods/` 和 `main/protocol/` 不得反向依赖 `main/analysis/`。

这一设计使 `minimal_method_package` 可以排除论文图表重建逻辑, 只保留读者理解和复用方法所需的最小代码。


## 实验矩阵覆盖率审计

论文结果重建链路可以额外消费 `experiment_matrix.json`, 并生成 `artifacts/paper_experiment_coverage_report.json`。该产物只比较矩阵声明和已有 records, 不重新运行 CEG 方法, 也不调用第三方 baseline。

该报告用于区分“链路可重建”和“正式实验矩阵已覆盖”两个概念。dry-run 可以生成完整图表与结果包, 但通常不会覆盖所有 split、attack_condition 和外部 baseline 组合; 正式论文实验可通过 `--require-experiment-coverage` 把该报告提升为失败门禁。

## 正式结果证据完整性门禁

`paper_readiness_report.json` 和 `paper_results_package_validation.json` 负责证明产物是否完整、可重建、摘要一致。对于论文正式结果, 还需要证明结果不是 dry-run fixture, 并且覆盖完整实验矩阵和标准水印指标。该项目使用:

```powershell
python scripts/validate_paper_result_evidence.py --target path\to\colab_run_bundle --require-external-command-results --require-pass
```

该门禁会检查 `event_records.json`、`paper_claim_audit.json`、`paper_experiment_coverage_report.json`、`method_group_comparison_table.csv`、`quality_metrics_summary.csv`、Colab bundle 中的 `provided_result_files_manifest.json` 以及外部命令结果。它不重新计算指标, 只审计已经生成的证据。

