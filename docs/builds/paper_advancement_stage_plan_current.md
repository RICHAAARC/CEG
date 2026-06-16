# CEG 当前向论文发表推进阶段计划

## 1. 文档定位

本文档保存于 `D:\Code\CEG\docs\builds\paper_advancement_stage_plan_current.md`。它用于记录 `D:\Code\CEG` 从当前真实 pilot 输入准备状态推进到“可供论文撰写和发表使用的结果包”的阶段计划。

整理日期: `2026-06-17`

本文档只记录当前真实状态、阶段边界、验收门禁和下一步执行顺序。它不把 dry-run、mock、rehearsal 或占位结果声明为论文正式实验结果。

## 2. 最终目标

最终目标是形成一个可供论文撰写和发表使用的结果包。该结果包必须能够支撑以下论文产物:

1. 主结果表: `TPR@FPR`、`attack TPR@FPR`、baseline comparison、quality metric。
2. 示例图: clean image、watermarked image、attacked image、comparison grid。
3. 机制分析: CEG 主方法、内部消融、外部 baseline 的统一记录。
4. 统计证据: fixed-FPR threshold table、TPR table、attack robustness table、statistical test report。
5. 治理证据: records、manifests、readiness report、claim audit、package manifest。
6. 归档产物: 按结果类型保存到 `D:\content\drive\MyDrive\CEG` 或 Colab 中的 `/content/drive/MyDrive/CEG`。

## 3. 当前阶段结论

当前阶段为:

```text
real_pilot_input_preparation
```

该阶段的含义是: 真实 pilot 工作区已经建立, 但 prompt、split、seed、model、watermark 等关键输入仍未填入真实值。因此当前不能进入真实图像生成、真实 attack、真实 detection、真实 baseline、真实 metric 或正式 fixed-FPR 统计阶段。

当前真实工作区为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500
```

当前最前置阻断点为:

```text
p0_input_preflight
```

当前关键报告状态为:

```text
pilot_input_value_pack_status_report.json: fail
pilot_input_value_pack_fill_sheet_import_report.json: fail
pilot_stage_progress_summary.json: fail
```

当前 `pilot_input_value_pack_status_report.json` 摘要为:

```text
value_entry_count = 19
filled_count = 0
missing_count = 19
placeholder_count = 0
invalid_count = 0
blocking_item_count = 19
```

当前 `pilot_stage_progress_summary.json` 摘要为:

```text
stage_count = 13
pass_count = 0
fail_count = 13
blocking_issue_count = 148
```

当前 CSV 填写表为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

当前 CSV 填写指南为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet_guidance.md
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet_guidance.json
```

当前导入报告失败原因是 `value_json` 列尚未填写, 19 个条目均为 `empty_value_json`。

## 4. 当前不能声明的内容

在 P0 阶段通过之前, 不能声明以下内容:

1. 不能声明已完成真实 SD 图像生成。
2. 不能声明已完成真实 watermark backend 运行。
3. 不能声明已完成正式 attack 实验。
4. 不能声明已完成 CEG detector 正式分数。
5. 不能声明已完成外部 baseline 真实对比。
6. 不能声明已完成 LPIPS、FID、CLIP score 等正式高级质量指标。
7. 不能声明已生成可支撑论文结论的 TPR@FPR 表。
8. 不能把 dry-run、mock 或 rehearsal 结果写成论文性能结论。
9. 不能绕过 records 和 manifests 手工拼接正式论文表格。

## 5. 阶段总览

| 阶段 | 名称 | 目标 | 当前状态 | 通过后进入 |
|---|---|---|---|---|
| P0 | 真实 pilot 输入冻结 | 填齐 prompt、split、seed、model、watermark 真实配置 | fail | P1 |
| P1 | 图像生成启动计划 | 生成可交给真实 SD / watermark backend 的命令计划 | fail | P2 |
| P2 | 真实图像与水印图像生成 | 产出 clean / watermarked 图像和 image manifests | fail | P3 |
| P3 | attack pilot | 产出 attacked 图像和 attack manifests | fail | P4 |
| P4 | CEG detection 与内部消融 | 产出 detection events、thresholds 和 execution manifest | fail | P5 / P7 |
| P5 | external baseline | 产出 baseline observations 和 baseline execution manifest | fail | P6 |
| P6 | quality metric | 产出 metric rows 和 metric execution manifest | fail | P7 |
| P7 | fixed-FPR / TPR@FPR 统计 | 生成论文主表和鲁棒性表 | fail | P8 |
| P8 | paper results package | 生成论文结果包 | fail | P9 |
| P9 | MyDrive 分类归档 | 生成 snapshot、zip 和 archive manifest | fail | 论文撰写准备 |

## 6. P0: 真实 pilot 输入冻结

### 6.1 目标

P0 的目标是把当前所有占位输入替换为真实实验配置, 并让输入预检、value pack 状态、value pack 应用和执行就绪门禁全部通过。

### 6.2 当前必须填写的值

需要在 `pilot_input_value_pack_fill_sheet.csv` 的 `value_json` 列填写以下 19 项真实值:

1. `prompt_text`
2. `prompt_family`
3. `license_note`
4. `split`
5. `sample_role`
6. `seed`
7. `seed_role`
8. `backend_type`
9. `model_id`
10. `scheduler`
11. `num_inference_steps`
12. `guidance_scale`
13. `image_size`
14. `requires_huggingface_token`
15. `watermark_method`
16. `payload_bits`
17. `watermark_strength`
18. `backend_command`
19. `evidence_path`

### 6.3 `value_json` 填写规则

`value_json` 必须是合法 JSON 值:

```text
字符串: "a realistic prompt text"
布尔值: true 或 false
整数: 12345
浮点数: 7.5
数组: [512, 512]
对象: {"strength": 0.15, "mode": "pilot"}
```

需要注意: 布尔值必须写为 `true` 或 `false`, 不能写为字符串 `"true"` 或 `"false"`。数组和对象必须使用 JSON 格式。

### 6.4 推荐命令

```text
python scripts/export_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
python scripts/export_pilot_input_value_pack_fill_sheet_guidance.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
python scripts/import_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
python scripts/build_pilot_input_value_pack_status.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
python scripts/apply_pilot_input_value_pack.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --value-pack D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_value_pack.draft.json --require-pass
python scripts/validate_pilot_input_plan_templates.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_plan_preflight_report.json --require-pass
python scripts/build_pilot_execution_readiness_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_execution_readiness_report.json --require-pass
```

### 6.5 P0 完成标准

```text
pilot_input_value_pack_fill_sheet_import_report.json: overall_decision = pass
pilot_input_value_pack_status_report.json: overall_decision = pass
pilot_input_value_pack_application_report.json: overall_decision = pass
pilot_input_plan_preflight_report.json: overall_decision = pass
pilot_execution_readiness_report.json: overall_decision = pass
```

## 7. P1: 图像生成启动计划

### 7.1 目标

P1 的目标是把 P0 冻结后的真实输入转换为外部图像生成 backend 可消费的命令计划。该阶段不直接生成图像, 只生成可执行计划和资源变量。

### 7.2 推荐命令

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_plan_report.json --require-pass
```

### 7.3 P1 完成标准

```text
pilot_image_generation_launch_plan_report.json: overall_decision = pass
pilot_image_generation_launch_plan_report.json: command_count > 0
```

## 8. P2: 真实图像与水印图像生成

### 8.1 目标

P2 的目标是调用真实 SD 或等价图像生成 backend, 并结合真实 watermark backend 产出 clean / watermarked 图像。

图像水印论文需要真实图像产物。接收门禁本身不运行 SD 模型, 但正式结果包必须包含真实图像或可复核的真实图像索引。

### 8.2 必须输出

```text
inputs/images/clean/*
inputs/images/watermarked/*
inputs/images/image_pairs.json
inputs/images/image_manifests/image_generation_manifest.json
inputs/images/image_manifests/image_pair_manifest.json
```

### 8.3 P2 输出验收命令

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

## 9. P3: attack pilot

### 9.1 目标

attack 是论文鲁棒性评价的必须流程, 但不应并入图像生成阶段。推荐边界如下:

```text
图像生成: prompt -> clean image / watermarked image
attack: watermarked image -> attacked image
检测: clean / watermarked / attacked image -> detection events
统计: detection events -> fixed-FPR / TPR@FPR tables
```

### 9.2 必须输出

```text
image_attacks/attacked_images/*
image_attacks/image_pairs_attacked.json
image_attacks/image_manifests/attacked_image_manifest.json
image_attacks/image_manifests/attack_shard_manifest.json
```

### 9.3 P3 输出验收命令

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

## 10. P4: CEG detection 与内部消融

### 10.1 目标

P4 的目标是对 clean、watermarked 和 attacked 图像产生统一 detection events, 同时覆盖 CEG 主方法和内部消融方法。

### 10.2 必须输出

```text
ceg_detection/detection_events.json
ceg_detection/detection_thresholds.json
ceg_detection/ceg_detection_execution_manifest.json
ceg_detection/ablation_observations.json
```

### 10.3 P4 输出验收命令

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

## 11. P5: external baseline

### 11.1 目标

P5 的目标是接入外部 baseline, 使论文可以比较 CEG 与其他图像水印方法。

目标 baseline 包括:

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 11.2 必须输出

```text
external_baselines/baseline_observations.json
external_baselines/baseline_execution_manifest.json
external_baselines/external_result_evidence_report.json
```

### 11.3 P5 输出验收命令

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline claim 应使用:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-formal-evidence --require-pass
```

## 12. P6: quality metric

### 12.1 目标

P6 的目标是补充图像质量、感知质量、文本一致性和水印恢复质量指标, 避免论文只报告检测性能。

指标建议:

```text
PSNR
SSIM
LPIPS
FID
CLIP score
bit accuracy
payload recovery rate
```

### 12.2 必须输出

```text
external_metrics/metric_rows.json
external_metrics/metric_execution_manifest.json
external_metrics/quality_metric_summary_table.csv
```

### 12.3 P6 输出验收命令

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric claim 应使用:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-formal-evidence --require-pass
```

## 13. P7: fixed-FPR / TPR@FPR 统计

### 13.1 目标

P7 的目标是生成论文主表所需的 fixed-FPR 统计结果。

统计口径必须为:

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive -> TPR@FPR
attacked positive -> attack TPR@FPR by attack_family and attack_condition
```

### 13.2 必须输出

```text
paper_outputs/artifacts/fixed_fpr_threshold_table.csv
paper_outputs/artifacts/tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/attack_tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/baseline_comparison_table.csv
paper_outputs/artifacts/statistical_test_report.json
```

### 13.3 P7 输出验收命令

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-pass
```

正式论文统计 claim 应使用:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-statistical-report --require-pass
```

## 14. P8: paper results package

### 14.1 目标

P8 的目标是形成可供论文撰写使用的结果包。该结果包应包含 records、tables、figures、image examples、reports 和 manifests。

### 14.2 必须包含

```text
paper_results_package/artifacts/*
paper_results_package/latex_tables/*
paper_results_package/rendered_figures/*
paper_results_package/pdf_figures/*
paper_results_package/image_examples/*
paper_results_package/image_example_manifest.json
paper_results_package/paper_results_report.md
paper_results_package/paper_readiness_report.json
paper_results_package/paper_claim_audit.json
paper_results_package/paper_result_evidence_report.json
paper_results_package/external_result_evidence_report.json
paper_results_package/paper_results_package_manifest.json
```

### 14.3 P8 输出验收命令

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-pass
```

正式论文结果包应使用:

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-evidence --require-image-examples --require-pass
```

## 15. P9: MyDrive 分类归档

### 15.1 目标

P9 的目标是把通过验收的 `paper_results_package` 按类型归档到 MyDrive, 形成可复核的快照、压缩包和归档 manifest。

### 15.2 目标目录

```text
D:/content/drive/MyDrive/CEG/package_snapshots/
D:/content/drive/MyDrive/CEG/package_archives/
D:/content/drive/MyDrive/CEG/package_manifests/
D:/content/drive/MyDrive/CEG/change_reports/
D:/content/drive/MyDrive/CEG/audit_reports/
```

### 15.3 P9 输出验收命令

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

如需限定 run_id:

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --run-id <run_id> --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

## 16. 与 CEG-WM 的方法机制对齐要求

`D:\Code\CEG` 后续必须继续与 `D:\Code\CEG-WM` 保持以下核心机制一致:

1. prompt、split、shard、experiment plan 先行。
2. calibration clean negative 与 test evaluation 严格分离。
3. attack 是独立鲁棒性阶段, 不并入图像生成阶段。
4. detection scores 必须进入统一 records。
5. external baseline 必须进入统一 observation 或 event schema。
6. fixed-FPR threshold table、TPR@FPR table 和 attack TPR table 必须由 records 重建。
7. paper package 只归档可追溯 artifacts, 不归档无 provenance 的手工结果。

## 17. 立即执行顺序

当前最短推进路径为:

```text
S1. 打开 pilot_input_value_pack_fill_sheet_guidance.md, 理解每个 value_json 的类型要求。
S2. 打开 pilot_input_value_pack_fill_sheet.csv。
S3. 填写 19 个 value_json, 确保均为合法 JSON 值。
S4. 运行 import_pilot_input_value_pack_fill_sheet.py --require-pass。
S5. 运行 build_pilot_input_value_pack_status.py。
S6. 确认 pilot_input_value_pack_status_report.json 通过。
S7. 运行 apply_pilot_input_value_pack.py --require-pass。
S8. 运行 validate_pilot_input_plan_templates.py --require-pass。
S9. 运行 build_pilot_execution_readiness_report.py --require-pass。
S10. 运行 build_pilot_image_generation_launch_plan.py --require-pass。
S11. 执行真实 SD / watermark backend。
S12. 验收 image generation outputs。
S13. 执行 attack pilot 并验收。
S14. 执行 CEG detection 并验收。
S15. 接入 external baseline 并验收。
S16. 接入 quality metric 并验收。
S17. 运行 fixed-FPR / TPR@FPR 统计并验收。
S18. 构建 paper_results_package 并验收。
S19. 归档到 MyDrive 并验收。
S20. 每完成一个阶段后运行 build_pilot_stage_progress_summary.py 更新阶段看板。
```

## 18. 下一步明确结论

当前下一步不是运行模型, 也不是统计 TPR@FPR。当前下一步是填写并导入:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

只有该 CSV 的 `value_json` 全部合法填写并通过 value pack 状态校验后, 才能继续进入图像生成启动计划、真实图像生成、attack、detection、baseline、metric 和 fixed-FPR 统计阶段。
