# CEG 向论文发表推进阶段计划

## 1. 文档定位

本文档保存于 `D:\Code\CEG\docs\builds\paper_publication_stage_plan.md`。它是当前 `D:\Code\CEG` 项目面向论文发表结果包的阶段推进计划, 用于统一回答以下执行问题:

1. 当前项目真实处于哪个阶段。
2. 当前最先需要解除的阻断点是什么。
3. 从 prompt 到水印图像、attack、检测、baseline、统计、论文图表和 MyDrive 归档的阶段顺序是什么。
4. 每个阶段的输入、输出、通过门禁和禁止事项是什么。
5. 哪些产物可以支持论文撰写, 哪些产物只能作为工程 dry-run 证据。

整理日期: `2026-06-17`

本文档是阶段计划文档, 不是实验结果文档。文档中的 `pass` / `fail` 只表示当前工程门禁状态, 不表示论文性能结论。

---

## 2. 最终目标

最终目标是形成一个可供论文撰写和发表使用的结果包。该结果包应能够直接支撑论文中的数据表格、统计图、示例水印图像、attack 鲁棒性分析、外部 baseline 对比、质量指标和可复核证据。

目标结果包至少包含以下类型:

| 类型 | 最小产物 | 论文用途 |
|---|---|---|
| 图像产物 | clean image, watermarked image, attacked image, comparison grid | 支撑方法展示和示例图 |
| 检测记录 | CEG detection events, thresholds, ablation observations | 支撑主方法和内部消融 |
| 外部 baseline | baseline observations, baseline execution manifest, evidence report | 支撑方法对比 |
| 质量指标 | PSNR, SSIM, LPIPS, FID, CLIP score, bit accuracy, payload recovery rate | 支撑视觉质量和水印恢复质量分析 |
| 固定 FPR 统计 | fixed-FPR threshold table, TPR@FPR table, attack TPR@FPR table | 支撑论文主表和鲁棒性表 |
| 论文治理 | paper readiness report, claim audit, evidence report, package manifest | 支撑可复核和投稿前检查 |
| 归档产物 | package snapshot, zip archive, archive manifest | 支撑复现实验和论文写作交付 |

正式结果必须按结果类型落盘到 `D:\content\drive\MyDrive\CEG` 或 Colab 环境中的 `/content/drive/MyDrive/CEG`。Git 仓库中的 `outputs/` 不能作为正式论文结果存放位置。

---

## 3. 当前真实状态

当前真实阶段为:

```text
p0_input_freeze
```

当前真实工作区为:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500
```

当前首个阻断点为:

```text
p0_csv_import
```

当前阻断原因:

```text
pilot_input_value_pack_fill_sheet.csv 中仍有 19 个 value_json 未填写。
```

因此, 当前不能继续声明以下事项:

1. 不能声明真实 SD 图像生成已经完成。
2. 不能声明真实 watermark backend 已经运行。
3. 不能声明 attack 实验已经完成。
4. 不能声明 CEG detector 已产生正式分数。
5. 不能声明外部 baseline 已完成真实对比。
6. 不能声明 LPIPS、FID、CLIP score 等高级质量指标已经完成。
7. 不能声明已经得到可用于论文结论的 `TPR@FPR`。
8. 不能将 dry-run、mock、rehearsal 结果写成论文性能结论。

当前最优先动作不是继续写统计表, 而是补齐并验证真实 pilot 输入。

---

## 4. 总体流水线

论文结果包必须遵循以下流水线:

```text
prompt / split / seed / model / watermark config
  -> clean image / watermarked image
  -> attacked image
  -> CEG detection events
  -> internal ablation observations
  -> external baseline observations
  -> quality metric rows
  -> fixed-FPR / TPR@FPR statistics
  -> paper tables / figures / image examples
  -> paper_results_package
  -> MyDrive classified archive
```

其中 attack 是鲁棒性结果的必须流程, 但它不属于图像生成阶段。推荐边界如下:

```text
图像生成: prompt -> clean image / watermarked image
attack: watermarked image -> attacked image
检测: clean / watermarked / attacked image -> detection events
baseline: external method outputs -> baseline observations
质量指标: image pairs / attacked images -> metric rows
统计: detection events / thresholds / baseline observations -> fixed-FPR / TPR@FPR tables
论文产物: records / manifests -> tables / figures / reports / package
归档: paper_results_package -> MyDrive snapshots / archives / manifests
```

---

## 5. 阶段总览

| 阶段 | 名称 | 目标 | 当前状态 | 进入下一阶段条件 |
|---|---|---|---:|---|
| P0 | 真实 pilot 输入冻结 | 补齐 prompt、split、seed、model、watermark 等真实配置 | fail | P0 聚合门禁全部 pass |
| P1 | 图像生成启动计划 | 生成真实 SD / watermark backend 可消费的命令计划 | blocked by P0 | launch plan pass |
| P2 | 真实图像与水印图像生成 | 产出 clean / watermarked 图像和 image manifests | blocked by P1 | image 输出接收门禁 pass |
| P3 | attack pilot | 产出 attacked 图像和 attack manifests | blocked by P2 | attack 输出接收门禁 pass |
| P4 | CEG detection 与内部消融 | 产出 detection events、thresholds 和 ablation observations | blocked by P3 | detection 输出接收门禁 pass |
| P5 | external baseline | 产出 baseline observations 和 baseline evidence | blocked by P4 | baseline 输出接收门禁 pass |
| P6 | quality metric | 产出 metric rows 和 metric execution manifest | blocked by P2/P3 | metric 输出接收门禁 pass |
| P7 | fixed-FPR / TPR@FPR 统计 | 生成论文主表和鲁棒性统计表 | blocked by P4/P5/P6 | fixed-FPR 门禁 pass |
| P8 | 论文示例图与图表重建 | 生成示例图、LaTeX 表、rendered figures 和 reports | blocked by P7 | claim audit / readiness pass |
| P9 | paper results package | 形成论文写作结果包 | blocked by P8 | package acceptance pass |
| P10 | MyDrive 分类归档 | 形成 snapshot、zip 和 archive manifest | blocked by P9 | archive acceptance pass |
| P11 | 正式论文实验 | pilot 通过后运行完整规模实验 | blocked by pilot | formal readiness pass |

---

## 6. P0: 真实 pilot 输入冻结

### 6.1 目标

P0 的作用是把当前所有草稿、占位或未冻结输入替换为真实实验配置, 并在进入图像生成前完成输入门禁。该阶段不生成论文结果, 只冻结实验输入。

### 6.2 当前必须填写的 19 个真实值

需要在以下文件中填写 `value_json`:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

字段清单如下:

| 序号 | 字段 | 含义 | JSON 类型要求 |
|---:|---|---|---|
| 1 | `prompt_text` | 真实图像生成 prompt | string |
| 2 | `prompt_family` | prompt 分组类别 | string |
| 3 | `license_note` | prompt 来源或授权说明 | string |
| 4 | `split` | calibration 或 test | string |
| 5 | `sample_role` | clean_negative 或 positive_source 等样本角色 | string |
| 6 | `seed` | 图像生成随机种子 | integer |
| 7 | `seed_role` | primary 或 replicate | string |
| 8 | `backend_type` | diffusers、external_command 或内部 backend 标识 | string |
| 9 | `model_id` | SD 模型 ID、本地路径或外部服务标识 | string |
| 10 | `scheduler` | 采样调度器名称 | string |
| 11 | `num_inference_steps` | 推理步数 | positive integer |
| 12 | `guidance_scale` | classifier-free guidance scale | positive number |
| 13 | `image_size` | 图像尺寸, 例如 `[512, 512]` | array |
| 14 | `requires_huggingface_token` | 是否需要 Hugging Face token | boolean |
| 15 | `watermark_method` | CEG 或外部水印方法名称 | string |
| 16 | `payload_bits` | payload bit 串或 payload 规则 | string / array / object |
| 17 | `watermark_strength` | 水印嵌入强度或方法参数 | number / object |
| 18 | `backend_command` | 外部命令或内部 backend 标识 | string |
| 19 | `evidence_path` | backend 日志或运行 manifest 路径 | string |

### 6.3 推荐执行命令

先导出填写表、填写指南和用户交接包:

```text
python scripts/export_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
python scripts/export_pilot_input_value_pack_fill_sheet_guidance.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
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


填写 CSV 后先执行只读预检。只读预检不得回写 value pack:

```text
python scripts/validate_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

只读预检通过后再导入 value pack:

```text
python scripts/import_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

然后运行 P0 dry-run 门禁:

```text
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --dry-run --require-pass
```

最后运行正式 P0 冻结:

```text
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

### 6.4 P0 完成标准

```text
pilot_input_value_pack_fill_sheet_validation_report.json: overall_decision = pass
pilot_input_value_pack_fill_sheet_import_report.json: overall_decision = pass
pilot_input_value_pack_status_report.json: overall_decision = pass
pilot_input_value_pack_application_report.json: overall_decision = pass
pilot_input_plan_preflight_report.json: overall_decision = pass
pilot_execution_readiness_report.json: overall_decision = pass
pilot_p0_input_freeze_report.json: overall_decision = pass
```

---

## 7. P1: 图像生成启动计划

### 7.1 目标

P1 将 P0 冻结后的真实输入转换为真实 SD / watermark backend 可消费的命令计划。该阶段只生成启动计划, 不直接生成图像。

### 7.2 推荐命令

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_plan_report.json --require-pass
```

### 7.3 完成标准

```text
pilot_image_generation_launch_plan_report.json: overall_decision = pass
pilot_image_generation_launch_plan_report.json: command_count > 0
```

---

## 8. P2: 真实图像与水印图像生成

### 8.1 目标

P2 调用真实 SD 或等价图像生成 backend, 并结合真实 watermark backend 产出 clean / watermarked 图像。

图像水印论文需要真实图像产物。工程 dry-run 可以验证目录和 manifest 契约, 但不能替代正式图像生成, 也不能支撑论文性能结论。

### 8.2 必须输出

```text
inputs/images/prompt_plan.json
inputs/images/clean/*
inputs/images/watermarked/*
inputs/images/image_pairs.json
inputs/images/image_manifests/image_generation_manifest.json
inputs/images/image_manifests/image_pair_manifest.json
```

### 8.3 接收门禁

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

---

## 9. P3: attack pilot

### 9.1 目标

P3 对 watermarked 图像施加最小 attack 集合, 产生 attacked 图像和 attack provenance。attack 是鲁棒性评价的必须流程, 但它应独立于图像生成阶段。

### 9.2 最小 attack 集合

```text
jpeg
resize
crop
gaussian_noise
gaussian_blur
brightness_contrast
```

### 9.3 必须输出

```text
image_attacks/attacked_images/*
image_attacks/image_pairs_attacked.json
image_attacks/image_manifests/attacked_image_manifest.json
image_attacks/image_manifests/attack_shard_manifest.json
```

### 9.4 接收门禁

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

---

## 10. P4: CEG detection 与内部消融

### 10.1 目标

P4 对 clean、watermarked 和 attacked 图像产生统一 detection events, 同时覆盖 CEG 主方法和内部消融方法。

### 10.2 必须输出

```text
ceg_detection/detection_events.json
ceg_detection/detection_thresholds.json
ceg_detection/ceg_detection_execution_manifest.json
ceg_detection/ablation_observations.json
```

### 10.3 detection event 最小字段

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

### 10.4 接收门禁

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

---

## 11. P5: external baseline

### 11.1 目标

P5 接入外部 baseline, 使论文可以比较 CEG 与其他图像水印方法。baseline 结果必须进入统一 observation schema, 不能作为独立手工表格拼接。

### 11.2 目标 baseline

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 11.3 必须输出

```text
external_baselines/baseline_observations.json
external_baselines/baseline_execution_manifest.json
external_baselines/external_result_evidence_report.json
```

### 11.4 接收门禁

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline claim 应使用:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-formal-evidence --require-pass
```

---

## 12. P6: quality metric

### 12.1 目标

P6 补充图像质量、感知质量、文本一致性和水印恢复质量指标, 避免论文只报告检测性能。

### 12.2 指标分层

```text
轻量 CPU 指标: MSE, MAE, PSNR, global SSIM
高级感知指标: LPIPS, FID, CLIP score
水印恢复指标: bit accuracy, payload recovery rate
```

### 12.3 必须输出

```text
external_metrics/metric_rows.json
external_metrics/metric_execution_manifest.json
external_metrics/quality_metric_summary_table.csv
```

### 12.4 接收门禁

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric claim 应使用:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-formal-evidence --require-pass
```

---

## 13. P7: fixed-FPR / TPR@FPR 统计

### 13.1 目标

P7 生成论文主表所需的 fixed-FPR 统计结果。TPR@FPR 不能从图像数量手工计算, 必须由 detection events、threshold records 和 manifests 重建。

### 13.2 统计口径

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive -> TPR@FPR
attacked positive -> attack TPR@FPR by attack_family and attack_condition
external baseline observations -> baseline comparison table
```

### 13.3 必须输出

```text
paper_outputs/artifacts/fixed_fpr_threshold_table.csv
paper_outputs/artifacts/tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/attack_tpr_at_fixed_fpr_table.csv
paper_outputs/artifacts/baseline_comparison_table.csv
paper_outputs/artifacts/statistical_test_report.json
```

### 13.4 接收门禁

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-pass
```

正式论文统计检验 claim 应使用:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-statistical-report --require-pass
```

---

## 14. P8: 论文示例图与图表重建

### 14.1 目标

P8 生成论文撰写可引用的示例水印图像、comparison grid、统计图和 LaTeX 表。

### 14.2 必须输出

```text
paper_results_package/image_examples/clean/*
paper_results_package/image_examples/watermarked/*
paper_results_package/image_examples/attacked/*
paper_results_package/image_examples/comparison_grids/*
paper_results_package/image_examples/image_example_manifest.json
paper_results_package/latex_tables/*
paper_results_package/rendered_figures/*
paper_results_package/paper_results_report.md
paper_results_package/paper_claim_audit.json
```

### 14.3 完成标准

```text
示例图文件真实存在。
示例图 manifest 可追溯 prompt、seed、method、attack 和 detection record。
LaTeX 表和 rendered figures 可由 records 与 manifests 重建。
paper_claim_audit.json 不使用占位字段支撑正式 claim。
```

---

## 15. P9: paper results package

### 15.1 目标

P9 将论文需要的 records、tables、figures、reports、manifests 和 image examples 组装为结果包。

### 15.2 接收门禁

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-pass
```

正式论文结果包应使用:

```text
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-evidence --require-image-examples --require-pass
```

### 15.3 完成标准

```text
paper_results_package_manifest.json 存在且 package_status = complete。
paper_results_package_validation.json 为 pass。
paper_readiness_report.json 与 paper_claim_audit.json 均为 pass。
fixed-FPR / TPR@FPR / attack TPR / baseline comparison 表格进入 artifacts。
LaTeX、rendered figures 和 PDF figure manifest 均存在。
正式论文包包含 paper_result_evidence_report.json 和 external_result_evidence_report.json。
正式论文包包含 image_example_manifest.json 及示例图文件。
```

---

## 16. P10: MyDrive 分类归档

### 16.1 目标

P10 将结果包按类型归档到 MyDrive, 形成可用于论文撰写、复核和分享的快照。

### 16.2 目标目录

```text
D:/content/drive/MyDrive/CEG/package_snapshots/
D:/content/drive/MyDrive/CEG/package_archives/
D:/content/drive/MyDrive/CEG/package_manifests/
D:/content/drive/MyDrive/CEG/change_reports/
D:/content/drive/MyDrive/CEG/audit_reports/
```

### 16.3 接收门禁

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

指定 run_id 时使用:

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --run-id <run_id> --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
```

---

## 17. P11: 正式论文实验

### 17.1 目标

在 pilot 通过后冻结正式实验配置, 执行完整规模实验并生成投稿可用结果包。

### 17.2 必须覆盖

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

### 17.3 完成标准

```text
paper_result_evidence_report.json = pass
paper_readiness_report.json = pass
paper_claim_audit.json = pass
colab_acceptance_report.json = pass
colab_formal_result_gap_report.json = ready_for_formal_claims
```

---

## 18. 当前立即执行计划

当前应按以下顺序推进:

1. 先补齐 `pilot_input_value_pack_fill_sheet.csv` 中 19 个真实 `value_json`。
2. 运行只读 CSV 预检, 确保不回写 value pack 且 `overall_decision = pass`。
3. 运行 CSV 导入, 生成 import report。
4. 运行 P0 dry-run 和正式 P0 冻结门禁。
5. P0 通过后生成 image generation launch plan。
6. 在 GPU / Colab / 外部 backend 上执行真实 clean / watermarked 图像生成。
7. 通过 image generation output acceptance。
8. 执行 attack pilot 并通过 attack output acceptance。
9. 执行 CEG detection 和内部消融并通过 detection output acceptance。
10. 接入至少一个真实 external baseline, 再逐步扩展至目标 baseline 集合。
11. 接入 quality metrics, 先保证轻量指标, 再补 LPIPS / FID / CLIP score 等高级指标。
12. 由 records 和 manifests 重建 fixed-FPR / TPR@FPR 统计表。
13. 重建论文示例图、LaTeX 表、rendered figures 和 reports。
14. 构建 paper_results_package。
15. 将 package 按类型归档到 MyDrive。
16. 根据 pilot 缺口修正后, 再冻结正式论文实验配置。

---

## 19. 不应优先执行的事项

1. 不应在 P0 未通过前继续声称已有正式图像、水印、attack 或 TPR@FPR 结果。
2. 不应手工拼接论文主表、baseline 表或 attack 鲁棒性表。
3. 不应手工挑选示例图并绕过 image_example_manifest。
4. 不应把本地 mock image 或 dry-run detection 当成正式论文性能证据。
5. 不应在没有 calibration / test split 的情况下报告 TPR@FPR。
6. 不应在没有外部 evidence report 的情况下使用 external baseline 或高级 metric 支撑正式 claim。
7. 不应修改 `D:\Code\CEG-WM` 以适配 `D:\Code\CEG` 当前结果。

---

## 20. 资源判断

### 20.1 本地 dry-run

本地 dry-run 应只验证:

```text
目录结构
manifest schema
命令链路
package export
readiness audit
claim audit
```

它不验证真实模型性能。

### 20.2 是否需要真实 SD 模型

正式图像水印论文结果需要真实图像生成或真实外部生成结果。原因是论文需要展示和统计真实 clean / watermarked / attacked 图像, dry-run 占位图不能支撑论文结论。

### 20.3 是否需要 Hugging Face 密钥

`CEG` 项目本身不应强依赖 Hugging Face token。是否需要 token 取决于所选 SD、CLIP、LPIPS、FID 或外部 baseline backend 是否使用 gated model 或私有模型权重。

### 20.4 显存资源预估

```text
工程 dry-run: CPU 即可。
SD 1.5 级别生成: 建议 8GB 到 12GB GPU 显存。
SDXL 级别生成: 建议 16GB 到 24GB GPU 显存。
CLIP / LPIPS / SSIM / PSNR: 通常 4GB 到 8GB GPU 或 CPU 小批量可运行。
FID: 取决于样本量, GPU 更快, CPU 可小规模验证。
多 baseline 并行正式实验: 建议 24GB 或更高显存, 或采用 shard 分批运行。
```

---

## 21. 与现有文档的关系

本文档是当前阶段计划的规范整理稿。相关文档如下:

| 文档 | 用途 |
|---|---|
| `docs/builds/ceg_method_mechanism.md` | CEG 项目方法机制整理 |
| `docs/builds/ceg_wm_method_alignment_audit.md` | CEG 与 CEG-WM 方法机制对齐审计 |
| `docs/builds/paper_advancement_stage_plan_current.md` | 旧版当前推进计划和背景说明 |
| `docs/builds/paper_publication_execution_stage_plan.md` | 旧版执行阶段计划 |
| `docs/builds/paper_publication_result_package_plan.md` | 论文结果包结构计划 |
| `docs/builds/paper_gpu_handoff_and_pause_plan.md` | 本地无 GPU 时的暂停点、真实 GPU 运行交接产物和恢复验收命令 |

后续若出现阶段变化, 应优先更新本文档中的“当前真实状态”和“当前立即执行计划”。

---

## 2026-06-17 当前执行状态补充

当前真实执行状态已经从 P0 阻断推进到 P2 GPU 暂停点。

```text
P0 真实 pilot 输入冻结: pass
P1 图像生成启动计划: pass
P2 真实图像与水印图像生成: wait_for_user_colab_gpu_execution
```

P0 使用的真实来源包括:

```text
prompt source = D:/Code/CEG-WM/prompts/paper_main_probe_10.txt
model_id = stabilityai/stable-diffusion-3.5-medium
num_inference_steps = 28
guidance_scale = 7.0
image_size = [512, 512]
requires_huggingface_token = true
hf_token_status = defined_in_colab_environment_not_written_to_disk
```

P2 GPU 交接目录:

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/gpu_handoff/p2_image_generation
```



可用以下仓库命令重新生成 P2 Colab 执行清单:

```text
python scripts/build_pilot_p2_gpu_handoff.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-ready
```

继续推进的唯一有效下一步是用户在 Colab GPU 环境中生成真实 clean / watermarked 图像并回传 manifests。当前不得用 mock 图像或 dry-run 结果替代 P2 论文证据。

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
/content/CEG/run_image_generation.py
```

但当前仓库内不存在对应的:

```text
D:/Code/CEG/run_image_generation.py
```

因此, 当前 P2 命令计划应理解为外部 SD / watermark backend 模板, 不能误认为仓库已经内置真实 SD3 图像生成脚本。用户在 Colab GPU 环境中继续 P2 时必须满足以下任一条件:

1. 在 `/content/CEG/run_image_generation.py` 位置提供真实外部 backend 入口。
2. 修改 `image_generation_command_plan.json`, 指向实际可运行的 Colab 图像生成 / 水印脚本。
3. 使用 Notebook 或其他外部 backend 直接生成 P2 必需输出, 但仍必须写出 `prompt_plan.json`、clean / watermarked 图像、`image_pairs.json` 和 image manifests。

无论采用哪种方式, 回传后都必须运行 P2 接收门禁, 不能仅凭命令运行完成判断 P2 通过。
