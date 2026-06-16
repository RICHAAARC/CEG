# CEG 论文发表执行阶段计划

## 1. 文档目的

本文档是面向执行的阶段计划, 与 `paper_advancement_stage_plan_current.md` 配套使用。前者回答“当前处于什么阶段以及下一步是什么”, 本文档回答“每个阶段应输入什么, 输出什么, 用什么门禁判断能否继续”。

整理日期: `2026-06-17`

## 2. 执行原则

1. Notebook 只作为调度入口, 不手写正式 records, tables, figures 或 reports。
2. 正式论文表格和图必须由 records 与 manifests 重建。
3. 真实运行产物保存到 MyDrive, 不写入 Git 仓库的 `outputs/` 作为正式结果。
4. dry-run 只验证契约和链路, 不支持论文性能 claim。
5. attack 是必须流程, 但属于独立阶段, 不能并入图像生成阶段。
6. external baseline 和高级 metric 若用于正式论文 claim, 必须有 evidence report。

## 3. 总体流水线

```text
prompt plan
  -> split / seed / model / watermark config
  -> clean image / watermarked image
  -> attacked image
  -> CEG detection events
  -> external baseline observations
  -> quality metric rows
  -> fixed-FPR / TPR@FPR statistics
  -> paper tables / figures / example images
  -> paper_results_package
```

## 4. 阶段 A: 真实 pilot 输入冻结

### 目标

把所有草稿输入替换为真实实验配置, 并确认不再含有阻断性 placeholder。

### 输入

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_value_pack.draft.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/prompt_plan.draft.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/split_plan.draft.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/seed_plan.draft.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/model_config.draft.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/watermark_config.draft.json
```

### 输出

```text
pilot_input_value_pack_application_report.json
pilot_input_plan_preflight_report.json
pilot_execution_readiness_report.json
```

### 通过条件

```text
overall_decision = pass
无阻断性 placeholder
真实 prompt / split / seed / model / watermark 配置已冻结
```

## 5. 阶段 B: 图像生成启动计划

### 目标

生成可交给真实 SD / watermark backend 的命令计划。

### 输出

```text
pilot_image_generation_launch_variables.draft.json
pilot_image_generation_launch_plan_report.json
```

### 通过条件

```text
command_count > 0
blocking_items = []
overall_decision = pass
```

## 6. 阶段 C: 真实图像与水印图像生成

### 目标

从 prompt 生成 clean 图像, 并生成对应 watermarked 图像。

### 输出目录

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/clean/
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/watermarked/
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_pairs.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_manifests/image_generation_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_manifests/image_pair_manifest.json
```

### 说明

这是需要真实 SD 模型或等价图像生成 backend 参与的阶段。接收门禁不负责生成图像, 只负责检查生成后的图像和 manifest 是否可用。

## 7. 阶段 C2: 图像生成输出接收门禁

### 命令

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

### 通过条件

```text
clean image 存在
watermarked image 存在
image_pairs.json 可读
image_generation_manifest.json 可读
image_pair_manifest.json 可读
manifest 计数与实际 image pair 可对齐
```

## 8. 阶段 D: attack pilot

### 目标

对 watermarked 图像施加最小 attack 集合, 产生 attacked 图像和 provenance。

### 最小 attack 集合

```text
jpeg
resize
crop
gaussian_noise
gaussian_blur
brightness_contrast
```

### 输出

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/attacked_images/*
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_pairs_attacked.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_manifests/attacked_image_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_manifests/attack_shard_manifest.json
```

## 9. 阶段 D2: attack 输出接收门禁

### 命令

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

### 通过条件

```text
attacked image 存在
每条记录包含 source watermarked image
每条记录包含 attack_family, attack_condition, attack_params 或 attack_parameters
attack manifest 与 attacked image 计数一致或有明确解释
```

## 10. 阶段 E: CEG detection 与内部消融

### 目标

对 clean, watermarked 和 attacked 图像产生统一 detection events。

### 输出

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/detection_events.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/detection_thresholds.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/ceg_detection_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/ablation_observations.json
```

### 记录要求

每条 detection event 至少应能表达:

```text
method_name
split
sample_role
score
higher_is_positive
is_watermarked
attack_family
attack_condition
source_image
run_id
provenance
```

## 11. 阶段 E2: detection 输出接收门禁

### 命令

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

### 通过条件

```text
detection_events.json 可读
detection_thresholds.json 可读
至少存在一个 detection run manifest
存在 calibration clean negative
存在 test clean negative
存在 test positive
threshold 选择与 test evaluation 分离
```

## 12. 阶段 F: external baseline pilot

### 目标

接入外部 baseline, 使论文能够比较 CEG 与外部方法。

### 目标 baseline

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 输出

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/baseline_observations.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/baseline_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/external_result_evidence_report.json
```

## 13. 阶段 F2: external baseline 输出接收门禁

### 命令

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline claim:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-formal-evidence --require-pass
```

### 通过条件

```text
baseline_observations.json 可读
baseline_execution_manifest.json 可读
baseline_id 来自 baseline registry
score 与 threshold 为数值
observation_count 与真实记录一致
正式 claim 时 external_result_evidence_report.json 必须 pass
```

## 14. 阶段 G: quality metric pilot

### 目标

为论文提供图像质量、感知质量、文本一致性和水印恢复质量指标。

### 输出

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/metric_rows.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/metric_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/quality_metric_summary_table.csv
```

### 指标分层

```text
轻量 CPU 指标: MSE, MAE, PSNR, global SSIM
高级感知指标: LPIPS, FID, CLIP score
水印恢复指标: bit accuracy, payload recovery rate
```

## 15. 阶段 G2: quality metric 输出接收门禁

### 命令

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric claim:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-formal-evidence --require-pass
```

### 通过条件

```text
metric_rows.json 可读
metric_execution_manifest.json 可读
metric row 能追溯到样本或图像
metric value 为数值
metric_count 与真实记录一致
正式高级 metric claim 时 evidence report 必须 pass
```

## 16. 阶段 H: fixed-FPR / TPR@FPR 统计

### 目标

生成论文主表所需的固定 FPR 统计结果。

### 统计口径

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive -> TPR@FPR
attacked positive -> attack TPR@FPR by attack_family and attack_condition
```

### 输出

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
baseline_comparison_table.csv
statistical_test_report.json
LaTeX tables
```

### 通过条件

```text
TPR@1%FPR 可复现
如果样本量足够, TPR@0.1%FPR 可复现
threshold selection 不使用 test split
attack TPR 按 attack_family 和 attack_condition 分组
所有表格可由 records 与 manifests 重建
```

## 17. 阶段 H2: fixed-FPR / TPR@FPR 统计输出接收门禁

### 命令

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root {workspace}/paper_outputs/artifacts --out {workspace}/pilot_fixed_fpr_output_acceptance_report.json --require-pass
```

正式论文统计检验声明应使用:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root {workspace}/paper_outputs/artifacts --out {workspace}/pilot_fixed_fpr_output_acceptance_report.json --require-statistical-report --require-pass
```

### 通过条件

```text
fixed_fpr_threshold_table.csv 存在且字段完整
tpr_at_fixed_fpr_table.csv 存在且字段完整
attack_tpr_at_fixed_fpr_table.csv 存在且字段完整
baseline_comparison_table.csv 存在且覆盖 TPR 表方法
所有 rate 字段位于 0 到 1 之间
所有 count 字段为非负整数
threshold 来源必须是 calibration_clean_negative
threshold 表、TPR 表和 attack TPR 表的 method / target_fpr 对齐
```

当前该命令已经实现。若 `paper_outputs/artifacts` 目录下缺少上述统计表, 门禁会失败并建议先运行 fixed-FPR 统计和论文产物重建。

## 18. 阶段 I: 论文示例图与图表重建

### 目标

生成论文撰写可引用的示例水印图像、comparison grid、统计图和 LaTeX 表。

### 输出

```text
image_examples/
image_example_manifest.json
rendered_figures/
pdf_figures/
latex_tables/
paper_results_report.md
paper_claim_audit.json
```

### 通过条件

```text
示例图文件真实存在
示例图可追溯 prompt, seed, method, attack 和 detection record
LaTeX 表和 rendered figures 可由 records 与 manifests 重建
paper_claim_audit.json 不使用 placeholder 字段支撑正式 claim
```

## 19. 阶段 J: MyDrive 结果包归档

### 目标

形成可交给论文写作和复核的结果包。

### 输出

```text
D:/content/drive/MyDrive/CEG/paper_results_package/
D:/content/drive/MyDrive/CEG/package_archives/paper_results_package.zip
D:/content/drive/MyDrive/CEG/package_manifests/paper_results_package_manifest.json
D:/content/drive/MyDrive/CEG/change_reports/
D:/content/drive/MyDrive/CEG/audit_reports/
```

### 通过条件

```text
paper_results_package_manifest.json 记录所有关键输入和输出
paper_readiness_report.json = pass 或明确列出非正式缺口
paper_result_evidence_report.json = pass
external_result_evidence_report.json = pass
paper_claim_audit.json = pass
```

## 20. 阶段 J2: paper_results_package 输出接收门禁

### 命令

```text
python scripts/validate_pilot_paper_results_package.py --package-root {workspace}/paper_results_package --out {workspace}/pilot_paper_results_package_acceptance_report.json --require-pass
```

正式论文结果包应使用:

```text
python scripts/validate_pilot_paper_results_package.py --package-root {workspace}/paper_results_package --out {workspace}/pilot_paper_results_package_acceptance_report.json --require-evidence --require-image-examples --require-pass
```

### 通过条件

```text
paper_results_package_manifest.json 存在且 package_status = complete
paper_results_package_validation.json 存在且 pass
paper_readiness_report.json 与 paper_claim_audit.json 均为 pass
fixed-FPR / TPR@FPR / attack TPR / baseline comparison 表格进入 artifacts
LaTeX、rendered figures 和 PDF figure manifest 均存在
正式论文包必须包含 paper_result_evidence_report.json 和 external_result_evidence_report.json
正式论文包必须包含 image_example_manifest.json 及示例图文件
```

当前该命令已经实现。若 `paper_results_package` 尚未导出或缺少核心论文产物, 门禁会失败并建议先重新运行结果包导出。

## 21. 阶段 K: 正式论文实验

### 目标

在 pilot 通过后冻结正式实验配置, 执行完整规模实验并生成投稿可用结果包。

### 必须覆盖

```text
完整 prompt set
完整 clean / watermarked / attacked images
完整 CEG + internal ablation
完整 external baselines
完整 quality metrics
完整 fixed-FPR / TPR@FPR
完整 paper figures
完整 LaTeX tables
完整 image examples 与 comparison grids
完整 paper_results_report.md
完整 paper_results_package.zip
完整 Colab 或 GPU 运行 bundle
```

## 22. 当前立即执行建议

当前立即执行优先级如下:

1. 补齐真实 pilot 输入 value pack。
2. 使 pilot input preflight 与 execution readiness 通过。
3. 生成并通过 image generation launch plan。
4. 执行真实图像和水印图像生成。
5. 逐级通过 image, attack, detection, baseline, metric 输出接收门禁。
6. 再进入 fixed-FPR / TPR@FPR 统计。
7. 最后构建 paper_results_package 并归档到 MyDrive。

其中, 工程侧已补齐 `quality metric 输出接收门禁`、`fixed-FPR 统计输出接收门禁` 和 `paper_results_package 输出接收门禁`。后续真实执行侧必须先补齐真实 pilot 输入, 再依次产出 image、attack、detection、baseline、metric 和 fixed-FPR 结果；只有这些接收门禁与结果包接收门禁通过后, 才应进入 MyDrive 归档。
