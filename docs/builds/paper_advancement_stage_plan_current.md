# CEG 当前向论文发表推进阶段计划

## 1. 文档定位

本文档保存于 `D:\Code\CEG\docs\builds\paper_advancement_stage_plan_current.md`。它是当前 `D:\Code\CEG` 项目向论文发表结果包推进的阶段计划总表, 用于回答以下问题:

1. 当前真实进度处于哪个阶段。
2. 下一步必须先完成什么。
3. 每个阶段的输入、输出、门禁和禁止事项是什么。
4. 哪些产物可以支撑论文撰写, 哪些产物只能作为工程 dry-run 或排障证据。
5. 如何保持 `D:\Code\CEG` 与 `D:\Code\CEG-WM` 的核心方法机制一致。

整理日期: `2026-06-17`

本文档是阶段计划文档, 不是实验结果文档。文档中的 fail / pass 只表示当前工作区的工程门禁状态, 不表示论文实验性能。

## 2. 最终目标

最终目标是形成一个可供论文撰写和发表使用的结果包。该结果包必须能够支撑论文中的表格、图像示例、方法对比、鲁棒性分析和可复核证据。

目标结果包至少应包含以下内容:

1. 主实验表格: `TPR@FPR`、`attack TPR@FPR`、baseline comparison、quality metric。
2. 示例图像: clean image、watermarked image、attacked image、comparison grid。
3. 方法机制材料: CEG 主方法、内部消融、外部 baseline 的统一 records 与 manifests。
4. 统计材料: fixed-FPR threshold table、TPR table、attack robustness table、statistical test report。
5. 论文治理材料: paper readiness report、claim audit、evidence report、package manifest。
6. 归档材料: 按结果类型保存到 `D:\content\drive\MyDrive\CEG` 或 Colab 中的 `/content/drive/MyDrive/CEG`。

## 3. 当前真实状态

当前阶段为:

```text
p0_input_freeze
```

当前真实工作区为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500
```

当前最前置阻断点为:

```text
p0_csv_import
```

阻断原因是 `pilot_input_value_pack_fill_sheet.csv` 中 19 个条目的 `value_json` 仍为空, 因此 P0 聚合门禁不能继续应用 value pack, 也不能进入输入模板预检和 execution readiness。

当前关键报告状态如下:

| 报告 | 当前结论 | 关键事实 |
|---|---:|---|
| `pilot_input_value_pack_status_report.json` | fail | `filled_count = 0`, `missing_count = 19` |
| `pilot_p0_input_freeze_report.json` | fail | P0 聚合门禁未通过 |
| `pilot_p0_input_freeze_dry_run_report.json` | fail | dry-run 首个阻断门禁为 `p0_csv_import` |
| `pilot_stage_progress_summary.json` | fail | `stage_count = 14`, `pass_count = 0`, `fail_count = 14`, `blocking_issue_count = 153` |

当前必须由人工或上游配置提供真实值的文件为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

填写说明文件为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet_guidance.md
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet_guidance.json
```

## 4. 当前不能声明的内容

在 P0 通过之前, 不能声明以下事项:

1. 不能声明真实 SD 图像生成已经完成。
2. 不能声明真实 watermark backend 已经运行。
3. 不能声明 attack 实验已经完成。
4. 不能声明 CEG detector 已经产生正式分数。
5. 不能声明外部 baseline 已经完成真实对比。
6. 不能声明 LPIPS、FID、CLIP score 等正式质量指标已经完成。
7. 不能声明已经得到可支撑论文结论的 `TPR@FPR`。
8. 不能把 dry-run、mock、rehearsal 结果写成论文性能结论。
9. 不能绕过 records 和 manifests 手工拼接正式论文表格或图。

## 5. 总体方法流水线

论文产物必须遵循以下流水线:

```text
prompt / split / seed / model / watermark config
  -> clean image / watermarked image
  -> attacked image
  -> CEG detection events
  -> external baseline observations
  -> quality metric rows
  -> fixed-FPR / TPR@FPR statistics
  -> paper tables / figures / image examples
  -> paper_results_package
  -> MyDrive archive
```

该流水线中, attack 是必须阶段, 但它不是图像生成阶段的一部分。推荐边界为:

```text
图像生成: prompt -> clean image / watermarked image
attack: watermarked image -> attacked image
检测: clean / watermarked / attacked image -> detection events
统计: detection events -> fixed-FPR / TPR@FPR tables
论文产物: records / manifests -> tables / figures / reports / package
```

## 6. 阶段总览

| 阶段 | 阶段名称 | 阶段目标 | 当前状态 | 通过后进入 |
|---|---|---|---:|---|
| P0 | 真实 pilot 输入冻结 | 填齐 prompt、split、seed、model、watermark 真实配置 | fail | P1 |
| P1 | 图像生成启动计划 | 生成真实 SD / watermark backend 可消费的命令计划 | fail | P2 |
| P2 | 真实图像与水印图像生成 | 产出 clean / watermarked 图像和 image manifests | fail | P3 |
| P3 | attack pilot | 产出 attacked 图像和 attack manifests | fail | P4 |
| P4 | CEG detection 与内部消融 | 产出 detection events、thresholds、ablation observations | fail | P5 / P7 |
| P5 | external baseline | 产出 baseline observations 和 baseline execution manifest | fail | P6 |
| P6 | quality metric | 产出 metric rows 和 metric execution manifest | fail | P7 |
| P7 | fixed-FPR / TPR@FPR 统计 | 生成论文主表、鲁棒性表和 baseline 对比表 | fail | P8 |
| P8 | paper results package | 生成论文结果包 | fail | P9 |
| P9 | MyDrive 分类归档 | 生成 snapshot、zip 和 archive manifest | fail | 论文撰写准备 |

## 7. P0: 真实 pilot 输入冻结

### 7.1 目标

P0 的目标是把当前所有占位输入替换为真实实验配置, 并让 CSV 导入、value pack 状态、value pack 应用、输入模板预检和执行就绪门禁全部通过。

### 7.2 必须填写的 19 个真实值

需要在 `pilot_input_value_pack_fill_sheet.csv` 的 `value_json` 列填写以下字段:

| 序号 | 字段 | 含义 | JSON 类型要求 |
|---:|---|---|---|
| 1 | `prompt_text` | 真实图像生成 prompt | 字符串 |
| 2 | `prompt_family` | prompt 分组类别 | 字符串 |
| 3 | `license_note` | prompt 来源或授权说明 | 字符串 |
| 4 | `split` | calibration 或 test | 字符串 |
| 5 | `sample_role` | clean_negative 或 positive_source 等样本角色 | 字符串 |
| 6 | `seed` | 图像生成随机种子 | 整数 |
| 7 | `seed_role` | primary 或 replicate | 字符串 |
| 8 | `backend_type` | diffusers、external_command 或内部 backend 标识 | 字符串 |
| 9 | `model_id` | SD 模型 ID、本地路径或外部服务标识 | 字符串 |
| 10 | `scheduler` | 采样调度器名称 | 字符串 |
| 11 | `num_inference_steps` | 推理步数 | 正整数 |
| 12 | `guidance_scale` | classifier-free guidance scale | 正数 |
| 13 | `image_size` | 图像尺寸 | 数组, 例如 `[512, 512]` |
| 14 | `requires_huggingface_token` | 是否需要 Hugging Face token | 布尔值 |
| 15 | `watermark_method` | CEG 或外部水印方法名称 | 字符串 |
| 16 | `payload_bits` | payload bit 串或 payload 规则 | 字符串、数组或对象 |
| 17 | `watermark_strength` | 水印嵌入强度或方法参数 | 数值或对象 |
| 18 | `backend_command` | 外部命令或内部 backend 标识 | 字符串 |
| 19 | `evidence_path` | backend 日志或运行 manifest 路径 | 字符串 |

### 7.3 `value_json` 填写规则

`value_json` 必须是合法 JSON 值:

```text
字符串: "a realistic prompt text"
布尔值: true 或 false
整数: 12345
浮点数: 7.5
数组: [512, 512]
对象: {"strength": 0.15, "mode": "pilot"}
```

布尔值必须写为 `true` 或 `false`, 不能写为字符串 `"true"` 或 `"false"`。

### 7.4 推荐命令

先导出填写表和填写指南:

```text
python scripts/export_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
python scripts/export_pilot_input_value_pack_fill_sheet_guidance.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

填写 CSV 后, 先运行隔离 dry-run:

```text
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --dry-run --require-pass
```

只有 dry-run 通过后, 才运行正式 P0 冻结:

```text
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

### 7.5 P0 完成标准

```text
pilot_p0_input_freeze_report.json: overall_decision = pass
pilot_input_value_pack_fill_sheet_import_report.json: overall_decision = pass
pilot_input_value_pack_status_report.json: overall_decision = pass
pilot_input_value_pack_application_report.json: overall_decision = pass
pilot_input_plan_preflight_report.json: overall_decision = pass
pilot_execution_readiness_report.json: overall_decision = pass
```

## 8. P1: 图像生成启动计划

### 8.1 目标

P1 的目标是把 P0 冻结后的真实输入转换为外部图像生成 backend 可消费的启动变量和命令计划。该阶段不直接生成图像。

### 8.2 推荐命令

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_plan_report.json --require-pass
```

### 8.3 P1 完成标准

```text
pilot_image_generation_launch_plan_report.json: overall_decision = pass
pilot_image_generation_launch_plan_report.json: command_count > 0
```

## 9. P2: 真实图像与水印图像生成

### 9.1 目标

P2 的目标是调用真实 SD 或等价图像生成 backend, 并结合真实 watermark backend 产出 clean / watermarked 图像。

图像水印论文需要真实图像产物。工程验收门禁本身不运行 SD 模型, 但正式结果包必须包含真实图像文件或可复核的真实图像索引。

### 9.2 必须输出

```text
inputs/images/prompt_plan.json
inputs/images/clean/*
inputs/images/watermarked/*
inputs/images/image_pairs.json
inputs/images/image_manifests/image_generation_manifest.json
inputs/images/image_manifests/image_pair_manifest.json
```

### 9.3 输出验收命令

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

## 10. P3: attack pilot

### 10.1 目标

P3 的目标是对 watermarked 图像施加最小 attack 集合, 产生 attacked 图像和 attack provenance。attack 是鲁棒性评价的必须流程, 但不并入图像生成阶段。

### 10.2 最小 attack 集合

```text
jpeg
resize
crop
gaussian_noise
gaussian_blur
brightness_contrast
```

### 10.3 必须输出

```text
image_attacks/attacked_images/*
image_attacks/image_pairs_attacked.json
image_attacks/image_manifests/attacked_image_manifest.json
image_attacks/image_manifests/attack_shard_manifest.json
```

### 10.4 输出验收命令

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

## 11. P4: CEG detection 与内部消融

### 11.1 目标

P4 的目标是对 clean、watermarked 和 attacked 图像产生统一 detection events, 同时覆盖 CEG 主方法和内部消融方法。

### 11.2 必须输出

```text
ceg_detection/detection_events.json
ceg_detection/detection_thresholds.json
ceg_detection/ceg_detection_execution_manifest.json
ceg_detection/ablation_observations.json
```

### 11.3 detection event 最小字段

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

### 11.4 输出验收命令

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

## 12. P5: external baseline

### 12.1 目标

P5 的目标是接入外部 baseline, 使论文可以比较 CEG 与其他图像水印方法。baseline 结果必须进入统一 observation schema, 不能作为独立手工表格拼接。

### 12.2 目标 baseline

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 12.3 必须输出

```text
external_baselines/baseline_observations.json
external_baselines/baseline_execution_manifest.json
external_baselines/external_result_evidence_report.json
```

### 12.4 输出验收命令

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline claim 应使用:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-formal-evidence --require-pass
```

## 13. P6: quality metric

### 13.1 目标

P6 的目标是补充图像质量、感知质量、文本一致性和水印恢复质量指标, 避免论文只报告检测性能。

### 13.2 指标分层

```text
轻量 CPU 指标: MSE, MAE, PSNR, global SSIM
高级感知指标: LPIPS, FID, CLIP score
水印恢复指标: bit accuracy, payload recovery rate
```

### 13.3 必须输出

```text
external_metrics/metric_rows.json
external_metrics/metric_execution_manifest.json
external_metrics/quality_metric_summary_table.csv
```

### 13.4 输出验收命令

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric claim 应使用:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-formal-evidence --require-pass
```

## 14. P7: fixed-FPR / TPR@FPR 统计

### 14.1 目标

P7 的目标是生成论文主表所需的 fixed-FPR 统计结果。TPR@FPR 不能直接从图像数量手工计算, 必须由 detection events、threshold records 和 manifests 重建。

### 14.2 统计口径

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive -> TPR@FPR
attacked positive -> attack TPR@FPR by attack_family and attack_condition
external baseline observations -> baseline comparison table
```

### 14.3 必须输出

```text
paper_outputs/artifacts/fixed_fpr_threshold_table.csv
paper_outputs/artifacts/tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/attack_tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/baseline_comparison_table.csv
paper_outputs/artifacts/statistical_test_report.json
```

### 14.4 输出验收命令

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-pass
```

正式论文统计 claim 应使用:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-statistical-report --require-pass
```

## 15. P8: paper results package

### 15.1 目标

P8 的目标是形成可供论文撰写使用的结果包。该结果包应包含 records、tables、figures、image examples、reports 和 manifests。

### 15.2 必须包含

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

### 15.3 输出验收命令

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-pass
```

正式论文结果包应使用:

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-evidence --require-image-examples --require-pass
```

## 16. P9: MyDrive 分类归档

### 16.1 目标

P9 的目标是把通过验收的 `paper_results_package` 按类型归档到 MyDrive, 形成可复核的快照、压缩包和归档 manifest。

### 16.2 目标目录

```text
D:/content/drive/MyDrive/CEG/package_snapshots/
D:/content/drive/MyDrive/CEG/package_archives/
D:/content/drive/MyDrive/CEG/package_manifests/
D:/content/drive/MyDrive/CEG/change_reports/
D:/content/drive/MyDrive/CEG/audit_reports/
```

### 16.3 输出验收命令

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

如需限定 run_id:

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --run-id <run_id> --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

## 17. 与 CEG-WM 的方法机制对齐要求

`D:\Code\CEG` 后续必须继续与 `D:\Code\CEG-WM` 保持以下核心机制一致:

1. prompt、split、shard、experiment plan 先行。
2. calibration clean negative 与 test evaluation 严格分离。
3. attack 是独立鲁棒性阶段, 不并入图像生成阶段。
4. detection scores 必须进入统一 records。
5. external baseline 必须进入统一 observation 或 event schema。
6. fixed-FPR threshold table、TPR@FPR table 和 attack TPR table 必须由 records 重建。
7. paper package 只归档可追溯 artifacts, 不归档无 provenance 的手工结果。
8. Notebook 只能调度 repository modules, 不能手工写正式 records、tables、figures 或 reports。

## 18. 当前立即执行顺序

当前最短推进路径为:

```text
S1. 打开 pilot_input_value_pack_fill_sheet_guidance.md, 理解每个 value_json 的类型要求。
S2. 打开 pilot_input_value_pack_fill_sheet.csv。
S3. 填写 19 个 value_json, 确保均为合法 JSON 值。
S4. 运行 build_pilot_p0_input_freeze_report.py --dry-run --require-pass, 确认填写值在隔离副本中可通过。
S5. 运行 build_pilot_p0_input_freeze_report.py --require-pass, 正式回写 value pack 并应用输入模板。
S6. 确认 P0 聚合报告、value pack 状态报告、输入模板预检报告和 execution readiness 报告均通过。
S7. 运行 build_pilot_image_generation_launch_plan.py --require-pass。
S8. 执行真实 SD / watermark backend。
S9. 验收 image generation outputs。
S10. 执行 attack pilot 并验收。
S11. 执行 CEG detection 与内部消融并验收。
S12. 接入 external baseline 并验收。
S13. 接入 quality metric 并验收。
S14. 运行 fixed-FPR / TPR@FPR 统计并验收。
S15. 构建 paper_results_package 并验收。
S16. 归档到 MyDrive 并验收。
S17. 每完成一个阶段后运行 build_pilot_stage_progress_summary.py 更新阶段看板。
```

## 19. 论文撰写可用性判定

只有满足以下条件后, 结果包才能作为论文撰写依据:

1. P2 存在真实 clean / watermarked 图像或可复核图像索引。
2. P3 存在真实 attacked 图像和 attack provenance。
3. P4 存在真实 detection events, 且 calibration 与 test 分离。
4. P5 baseline observations 可追溯到 baseline execution manifest。
5. P6 metric rows 可追溯到样本、图像或检测记录。
6. P7 所有 fixed-FPR / TPR@FPR 表格均可由 records 与 manifests 重建。
7. P8 结果包中的示例图、LaTeX 表、报告和 claim audit 均有 provenance。
8. P9 MyDrive archive manifest 与 zip / snapshot 内容一致。

## 20. 下一步明确结论

历史记录: 在 P0 通过之前, 下一步不是运行模型, 也不是统计 `TPR@FPR`, 而是填写并导入:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

填写前应先阅读:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet_guidance.md
```

填写完成后优先运行:

```text
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --dry-run --require-pass
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

当前该 CSV 已填写并通过 P0 聚合门禁, 且 P1 图像生成启动计划已经通过。当前停在 P2 真实图像与水印图像生成。

---

## 10. 阶段计划规范整理稿

当前阶段计划的规范整理稿已经更新到:

```text
docs/builds/paper_publication_stage_plan.md
```

后续若需要回答“当前向论文推进的阶段顺序、阻断点、门禁和立即下一步是什么”, 优先读取该文档。本文档保留较完整的背景说明和历史推进记录。

---

## 11. GPU 交接与暂停计划

由于当前本地没有 GPU 环境, 真实 SD / watermark / detector / baseline / 高级 metric 执行需要在到达对应阶段后暂停并交给用户运行。交接边界、需要交回的产物目录和恢复验收命令已经整理到:

```text
docs/builds/paper_gpu_handoff_and_pause_plan.md
```

历史记录: 该段原用于说明 P0 未通过时的 GPU 暂停规则。当前 P0 和 P1 已通过, 已到达 P2 GPU 暂停点。

P0 用户交接包可通过以下命令生成:

```text
python scripts/build_pilot_p0_input_handoff_bundle.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

填写交接包内 CSV 后, 可直接运行以下命令验证并应用交接包。该命令只有在预检通过时才会同步 canonical CSV 并导入 value pack:

```text
python scripts/apply_pilot_p0_input_handoff_bundle.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```
交接包本身可用以下命令验收。该命令只判断 handoff 文件是否完整和安全, 不代表 P0 已通过:

```text
python scripts/validate_pilot_p0_input_handoff_bundle.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-apply-report --require-pass
```


默认输出目录为:

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/user_handoff/p0_input_handoff/
```

---

## 21. 2026-06-17 P0 / P1 最新推进状态

根据当前真实工作区报告, P0 与 P1 已经通过, 项目已推进到 P2 GPU 图像生成暂停点。

当前真实工作区仍为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs
eal_pilot_input_workspace_20260617_034500
```

已完成事项:

1. 已使用 `D:\Code\CEG-WM\prompts\paper_main_probe_10.txt` 作为 pilot prompt 来源。
2. 已记录用户确认的 Hugging Face token 状态: token 已在 Colab 环境定义, 不写入仓库、CSV、manifest 或日志。
3. 已将 19 个 `value_json` 写入 canonical CSV 和 handoff CSV。
4. `validate_pilot_input_value_pack_fill_sheet.py --require-pass` 已通过。
5. `apply_pilot_p0_input_handoff_bundle.py --require-pass` 已通过。
6. P0 dry-run 已通过。
7. P0 正式 freeze 已通过。
8. P1 image generation launch plan 已通过。
9. `pilot_stage_progress_summary.json` 已更新, 当前阶段为 `p2_image_generation_outputs`。

当前阶段看板关键事实:

```text
current_stage = p2_image_generation_outputs
pass_count = 6
fail_count = 8
recommended_next_action = 运行真实 SD / watermark backend, 写出 clean / watermarked 图像和 image manifests。
```

当前暂停原因:

```text
本地没有 GPU 环境, P2 需要用户在 Colab GPU 环境运行真实 SD3 / CEG-WM 水印图像生成。
```

P2 GPU 交接目录已经生成:

```text
D:\content\drive\MyDrive\CEG\pilot_runs
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\gpu_handoff\p2_image_generation
```

交接目录中的关键文件:

```text
p2_image_generation_gpu_handoff_manifest.json
p2_image_generation_gpu_handoff_readme.md
p2_image_generation_colab_execution_checklist.json
p2_image_generation_colab_runbook.md
```

可用以下仓库命令重新生成 P2 Colab 执行清单:

```text
python scripts/build_pilot_p2_gpu_handoff.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-ready
```


用户完成 Colab GPU 图像生成并回传输出后, 本地恢复验收命令为:

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
python scripts/build_pilot_stage_progress_summary.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

注意: 当前不能继续本地伪造 P2 输出。P2 必须产出真实 clean / watermarked 图像和 image manifests 后, 才能进入 P3 attack pilot。

### P2 Colab 路径转换说明

`build_pilot_p2_gpu_handoff.py` 现在会同时写出三类命令:

1. `command_plan`: 保留 P1 生成的原始 Windows 命令计划, 用于审计来源。
2. `colab_shell_commands`: 将 `D:/Code/CEG` 转换为 `/content/CEG`, 将 `D:/content/drive/MyDrive/CEG` 转换为 `/content/drive/MyDrive/CEG`, 可在 Colab 中复制执行。
3. `colab_acceptance_commands`: 在 Colab 中自检 P2 输出是否满足接收门禁。
4. `local_acceptance_commands`: 回到 Windows 本地后复核同一份 MyDrive 工作区。

该设计避免用户在 Colab GPU 环境中手工改路径, 同时保留原始 Windows 命令计划作为 provenance。

### P2 外部 backend 入口检查

当前 P2 handoff 会生成 `entrypoint_checks` 和 `execution_warnings`。该检查发现当前命令计划中的 Colab 入口为:

```text
/content/CEG/scripts/run_pilot_image_generation_backend.py
```

但当前仓库内不存在对应的:

```text
D:/Code/CEG/scripts/run_pilot_image_generation_backend.py
```

因此, 当前 P2 命令计划应理解为外部 SD / watermark backend 模板, 不能误认为仓库已经内置真实 SD3 图像生成脚本。用户在 Colab GPU 环境中继续 P2 时必须满足以下任一条件:

1. 在 `/content/CEG/scripts/run_pilot_image_generation_backend.py` 位置提供真实外部 backend 入口。
2. 修改 `image_generation_command_plan.json`, 指向实际可运行的 Colab 图像生成 / 水印脚本。
3. 使用 Notebook 或其他外部 backend 直接生成 P2 必需输出, 但仍必须写出 `prompt_plan.json`、clean / watermarked 图像、`image_pairs.json` 和 image manifests。

无论采用哪种方式, 回传后都必须运行 P2 接收门禁, 不能仅凭命令运行完成判断 P2 通过。

## 28. 2026-06-17 P2 真实图像生成交接更新

### 28.1 已确认的输入条件

1. Prompt 来源已确认: `D:/Code/CEG-WM/prompts`。
2. 当前 pilot prompt draft 已记录来源说明, 文件位于:
   `D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/prompt_plan.draft.json`。
3. Hugging Face token 状态已确认: 用户已在 Colab 环境定义 token。
4. token 仍不得写入仓库、CSV、manifest、Notebook 输出或日志。

### 28.2 P2 backend 入口状态

仓库已新增 P2 包装入口:

```text
D:/Code/CEG/scripts/run_pilot_image_generation_backend.py
```

该入口只负责调用真实外部 SD / watermark backend 并运行 P2 接收门禁。它不内置 Stable Diffusion 模型, 不自行生成水印图像, 也不会用 mock 图像冒充正式论文结果。

当前 Colab command plan 已更新为仓库内可定位入口:

```text
python /content/CEG/scripts/run_pilot_image_generation_backend.py --prompt-plan /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/prompt_plan.draft.json --out /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --model-config /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/model_config.draft.json
```

### 28.3 当前仍未完成的事项

当前命令计划已经不再缺少仓库入口, 但仍有一个执行前 warning:

```text
command_file_draft_placeholder
```

含义是: 正式 Colab 执行前, 需要通过 `--external-command-json` 或 `--external-command` 追加真实 SD / watermark backend 命令。该 backend 必须最终产出 P2 接收门禁要求的文件:

```text
inputs/images/prompt_plan.json
inputs/images/clean/*
inputs/images/watermarked/*
inputs/images/image_pairs.json
inputs/images/image_manifests/image_generation_manifest.json
inputs/images/image_manifests/image_pair_manifest.json
```

### 28.4 阶段结论

P0 和 P1 已通过。P2 已具备 Colab GPU handoff 和仓库内包装入口, 但尚未获得真实 GPU 生成的 clean / watermarked 图像与 manifests。因此当前阶段仍停留在 `p2_image_generation_outputs`, 不能进入 attack 或 TPR@FPR 统计阶段。

## 29. 2026-06-17 P2 外部 backend 命令草稿落盘

### 29.1 新增落盘文件

真实工作区已生成外部 backend 命令草稿:

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/p2_external_backend_command.draft.json
```

该文件目前仍包含 `external_command_placeholder`, 因此不能作为正式命令执行。用户在 Colab 中需要把该字段替换为 `external_command`, 值必须是真实 SD / watermark backend 的 argv 字符串列表。

### 29.2 当前可复制 Colab 包装命令

```text
python /content/CEG/scripts/run_pilot_image_generation_backend.py --prompt-plan /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/prompt_plan.draft.json --out /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --model-config /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/model_config.draft.json --external-command-json-file /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/p2_external_backend_command.draft.json
```

### 29.3 当前 warning 的精确定义

```text
command_file_draft_placeholder
```

含义是: 仓库内 P2 包装入口和命令文件路径均已具备, 但命令文件尚未替换为真实 GPU backend。该状态下仍不能进入 P3 attack, 也不能统计 TPR@FPR。

## 30. 2026-06-17 P2 外部 backend 命令校验器

### 30.1 新增能力

为了减少用户在 Colab 中手工修改 JSON 出错, 当前项目新增两个辅助入口:

```text
scripts/apply_pilot_image_generation_backend_command.py
scripts/validate_pilot_image_generation_backend_command.py
```

`apply_pilot_image_generation_backend_command.py` 用于把真实 SD / watermark backend 的 argv 写入 `p2_external_backend_command.draft.json` 的 `external_command` 字段。该脚本只写命令文件, 不运行模型。

`validate_pilot_image_generation_backend_command.py` 用于检查命令文件是否仍含 placeholder、是否缺少 `external_command`、是否把疑似 Hugging Face token 或 OpenAI token 直接写入命令文件。该脚本也不运行模型。

### 30.2 当前真实工作区校验状态

当前工作区命令文件仍为草稿, 校验报告已落盘:

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/p2_external_backend_command_validation_report.json
```

当前结论:

```text
overall_decision = fail
recommended_next_stage = replace_external_backend_command
```

这是预期状态, 因为真实 backend 命令尚未由用户在 Colab 中填写。

### 30.3 Colab 中推荐顺序

1. 准备真实 SD / watermark backend。
2. 使用 `apply_pilot_image_generation_backend_command.py` 写入真实 argv, 或手工把 `external_command_placeholder` 改为 `external_command`。
3. 运行:

```text
python scripts/validate_pilot_image_generation_backend_command.py --command-file /content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/configs/p2_external_backend_command.draft.json --require-ready
```

4. 校验通过后, 再运行 P2 包装命令生成真实 clean / watermarked 图像。
5. P2 接收门禁通过后, 才能进入 attack 和 TPR@FPR 统计。

## 31. 2026-06-17 P2 回传后的 P3 / P4 接续计划

### 31.1 新增接续计划产物

为了避免 P2 真实 GPU 图像回传后再次手工推导后续命令, 当前已生成接续计划:

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/gpu_handoff/post_p2_resume/pilot_post_p2_resume_plan.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/gpu_handoff/post_p2_resume/pilot_post_p2_resume_runbook.md
```

该计划当前状态为:

```text
overall_decision = blocked_until_p2_pass
```

这是正确状态, 因为 P2 图像生成输出尚未通过接收门禁。

### 31.2 P2 通过后的接续顺序

P2 接收门禁通过后, 接续计划会提供以下命令顺序:

1. `run_image_attack_workflow.py`: 基于 `inputs/images/image_pairs.json` 生成 attacked 图像和 attack manifests。
2. `validate_pilot_attack_outputs.py`: 验收 P3 attack 输出。
3. `run_ceg_detection_producer.py`: 生成 detection events / thresholds / producer manifest。
4. `validate_pilot_detection_outputs.py`: 验收 P4 detection 输出。
5. `build_pilot_stage_progress_summary.py`: 刷新阶段进度。

### 31.3 边界说明

`run_ceg_detection_producer.py` 是契约 dry-run producer, 不是正式检测模型。它用于验证 detection records、fixed-FPR 前置字段和结果包链路。正式论文结果仍需要真实 detector 或经认可的正式 detection backend 输出。

如果 P2 `image_pairs.json` 未覆盖 calibration clean negative、test clean negative 和 test positive, 后续 P4 / P7 仍会阻断。这不是脚本错误, 而是 fixed-FPR 统计所需样本角色不足。

## 32. 2026-06-17 P2 专用 Notebook 补充

### 32.1 新增 Notebook

当前已补充 P2 专用 Colab 入口:

```text
D:/Code/CEG/paper_workflow/colab_p2_image_generation.ipynb
```

该 Notebook 用于在 Colab GPU 环境中编排 `p2_image_generation_outputs` 阶段。它不会直接手写正式 P2 manifests, 而是调用以下仓库脚本:

```text
scripts/apply_pilot_image_generation_backend_command.py
scripts/validate_pilot_image_generation_backend_command.py
scripts/run_pilot_image_generation_backend.py
scripts/validate_pilot_image_generation_outputs.py
scripts/build_pilot_stage_progress_summary.py
scripts/build_pilot_post_p2_resume_plan.py
```

### 32.2 使用边界

该 Notebook 仍然需要真实外部 SD / watermark backend。若 `RUN_P2_IMAGE_GENERATION = False`, Notebook 只打印命令而不执行真实 GPU 生成。若要正式产出 P2, 必须先让 `p2_external_backend_command.draft.json` 中的 `external_command` 指向真实 backend, 并使命令文件校验通过。

P2 是否完成只以 `pilot_image_generation_output_acceptance_report.json` 中 `overall_decision = pass` 为准。
