# CEG 当前向论文发表推进阶段计划

## 1. 文档定位

本文档是 `D:/Code/CEG/docs/builds` 下的当前阶段计划快照, 用于把 `D:/Code/CEG` 从工程治理与 dry-run 链路推进到可供论文撰写和发表使用的结果包。

整理日期: `2026-06-17`

本文档只记录当前真实状态和下一步执行顺序, 不把 dry-run, rehearsal 或 mock 结果声明为论文正式结果。

## 2. 总目标

最终目标是形成一个可供论文撰写和发表使用的结果包。该结果包必须能够提供:

1. 论文主表所需的 `TPR@FPR`, `attack TPR@FPR`, baseline comparison 和 quality metric 数据。
2. 可复核的 clean / watermarked / attacked 图像索引, 以及少量可用于论文展示的水印图像示例。
3. CEG 方法、内部消融和外部 baseline 的统一统计记录。
4. 所有表格、图、报告和 claim audit 的 provenance, 使论文结果可由 records 与 manifests 重建。
5. MyDrive 归档产物, 根目录为 `D:/content/drive/MyDrive/CEG` 或 Colab 中的 `/content/drive/MyDrive/CEG`。

## 3. 当前阶段名称

```text
real_pilot_input_preparation
```

该阶段的含义是: 真实 pilot 工作区已经创建, 但关键输入配置仍处于草稿或占位状态。当前不能直接进入正式实验结论阶段, 必须先补齐真实输入, 再逐级通过 image generation, attack, detection, baseline, metric 和 fixed-FPR 的接收门禁。

通用工程写法是先冻结实验输入, 再运行小规模 pilot。项目特定写法是把该流程拆成 preflight, replacement checklist, value pack, execution readiness, launch plan 和多个输出接收门禁, 以保证论文结果不会由不可追溯文件手工拼接而来。

## 4. 当前真实工作区

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

该目录属于运行产物区, 不是 Git 仓库内的正式源码目录。后续真实图像、攻击结果、检测结果、baseline 结果、metric 结果和结果包均应按类型保存在 MyDrive 子目录中。

## 5. 当前已落地的门禁与真实状态

| 顺序 | 阶段或门禁 | 当前产物 | 当前状态 | 说明 |
|---:|---|---|---|---|
| 1 | pilot 输入模板预检 | `pilot_input_plan_preflight_report.json` | fail | 仍存在占位字段, 不能启动真实 SD / watermark。 |
| 2 | replacement checklist | `pilot_input_plan_replacement_checklist.json`, `.md` | fail | 已列出需要替换的真实值任务。 |
| 3 | value pack 应用 | `pilot_input_value_pack_application_report.json` | fail | 真实 `value` 尚未填入或尚未完整应用。 |
| 4 | execution readiness | `pilot_execution_readiness_report.json` | fail | 真实输入未冻结, 不能进入执行阶段。 |
| 5 | image generation launch plan | `pilot_image_generation_launch_plan_report.json` | fail | 尚无可执行真实图像生成命令计划。 |
| 6 | image generation 输出接收 | `pilot_image_generation_output_acceptance_report.json` | fail | clean / watermarked 图像和 manifest 尚未满足接收契约。 |
| 7 | attack 输出接收 | `pilot_attack_output_acceptance_report.json` | fail | attacked 图像和 attack manifest 尚未满足接收契约。 |
| 8 | detection 输出接收 | `pilot_detection_output_acceptance_report.json` | fail | detection events / thresholds 尚未满足 fixed-FPR 统计契约。 |
| 9 | baseline 输出接收 | `pilot_baseline_output_acceptance_report.json` | fail | external baseline observations 尚未满足论文对比契约。 |
| 10 | quality metric 输出接收 | `pilot_metric_output_acceptance_report.json` | fail | metric rows 与 execution manifest 尚未满足论文质量指标契约。 |
| 11 | fixed-FPR 统计输出接收 | `pilot_fixed_fpr_output_acceptance_report.json` | fail | fixed-FPR / TPR@FPR 论文主表尚未由真实 records 重建。 |
| 12 | paper results package 输出接收 | `pilot_paper_results_package_acceptance_report.json` | fail | paper_results_package 尚未导出并通过独立接收门禁。 |
| 13 | MyDrive 归档输出接收 | `pilot_mydrive_archive_acceptance_report.json` | fail | package_snapshots、package_archives 和 package_manifests 尚未形成可复核归档。 |
| 14 | value pack 填写状态汇总 | `pilot_input_value_pack_status_report.json`, `.md` | fail | 汇总仍未填写的真实输入 value 条目。 |
| 15 | pilot 阶段进度汇总 | `pilot_stage_progress_summary.json`, `.md` | fail | 汇总所有门禁状态, 指向首个真实执行阻断点。 |

## 6. 不能声明的内容

当前项目不能声明以下事项:

1. 不能声明已完成真实 SD 图像生成正式实验。
2. 不能声明已完成真实 watermark backend 正式实验。
3. 不能声明已完成真实 attack 全流程实验。
4. 不能声明已完成真实 CEG detector 全量评分。
5. 不能声明已完成 external baseline 真实对比。
6. 不能声明已完成 LPIPS, FID, CLIP score 等高级质量指标的正式结果。
7. 不能把 rehearsal, dry-run 或 mock 数值写成论文性能结论。
8. 不能把仍含 `_placeholder` 字段的配置作为真实 pilot 输入。

## 7. 向论文推进的阶段路线

### P0: 补齐真实 pilot 输入

目标: 把 prompt, split, seed, model, watermark 等草稿配置中的占位字段替换为真实实验值。

必须完成:

1. 填写 `pilot_input_value_pack.draft.json` 中的真实 `value`。
2. 应用 value pack 到 prompt / split / seed / model / watermark 计划文件。
3. 重新运行 pilot input preflight, 并要求通过。
4. 重新运行 execution readiness, 并要求通过。

推荐命令:

```text
python scripts/apply_pilot_input_value_pack.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --value-pack D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_value_pack.draft.json --require-pass
python scripts/validate_pilot_input_plan_templates.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_plan_preflight_report.json --require-pass
python scripts/build_pilot_execution_readiness_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_execution_readiness_report.json --require-pass
```

完成门禁:

```text
pilot_input_plan_preflight_report.json: overall_decision = pass
pilot_input_value_pack_application_report.json: overall_decision = pass
pilot_execution_readiness_report.json: overall_decision = pass
```

### P0.5: value pack 填写状态汇总

目标: 在不伪造真实实验值的前提下, 把 `pilot_input_value_pack.draft.json` 中仍未填写的 `value` 条目整理为 JSON 和 Markdown, 便于逐项补齐真实 prompt、split、seed、model 和 watermark 配置。

推荐命令:

```text
python scripts/build_pilot_input_value_pack_status.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

输出:

```text
pilot_input_value_pack_status_report.json
pilot_input_value_pack_status_report.md
```

完成门禁:

```text
pilot_input_value_pack_status_report.json: overall_decision = pass
pilot_input_value_pack_status_report.json: recommended_next_stage = apply_pilot_input_value_pack
```

说明: 该报告不替代 value pack 应用门禁, 只用于把当前最前置阻断点拆成可填写的真实输入清单。

### P1: 生成真实图像生成启动计划

目标: 将真实输入配置转换为外部图像生成 backend 可以消费的命令计划。

推荐命令:

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_plan_report.json --require-pass
```

完成门禁:

```text
pilot_image_generation_launch_plan_report.json: overall_decision = pass
pilot_image_generation_launch_plan_report.json: command_count > 0
```

### P2: 运行真实图像生成与水印生成

目标: 执行真实 SD / watermark backend, 产出 clean / watermarked 图像和图像级 manifest。

必须输出:

```text
inputs/images/prompt_plan.json
inputs/images/image_pairs.json
inputs/images/image_manifests/image_generation_manifest.json
inputs/images/image_manifests/image_pair_manifest.json
inputs/images/clean/*
inputs/images/watermarked/*
```

说明: 图像水印方法需要真实生成模型或真实图像生成 backend 参与。输出接收门禁本身不运行 SD 模型, 但它检查真实 backend 写出的文件是否满足后续 attack, detection 和统计链路的输入契约。

### P2.5: 图像生成输出接收门禁

目标: 验证 clean / watermarked 图像与 image manifest 是否可被后续流程消费。

推荐命令:

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

完成门禁:

```text
pilot_image_generation_output_acceptance_report.json: overall_decision = pass
pilot_image_generation_output_acceptance_report.json: recommended_next_stage = image_attack_pilot
```

### P3: 执行 attack pilot

目标: 基于 watermarked 图像执行最小 attack 集合, 评估鲁棒性。

attack 是论文流程的必须阶段, 但不应并入图像生成阶段。推荐边界如下:

```text
图像生成阶段: prompt -> clean image / watermarked image
attack 阶段: watermarked image -> attacked image
检测阶段: clean / watermarked / attacked image -> detection events
统计阶段: detection events -> fixed-FPR / TPR@FPR 表格
```

必须输出:

```text
image_attacks/attacked_image_manifest.json
image_attacks/attack_shard_manifest.json
image_attacks/image_pairs_attacked.json
image_attacks/attacked_images/*
```

### P3.5: attack 输出接收门禁

推荐命令:

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

完成门禁:

```text
pilot_attack_output_acceptance_report.json: overall_decision = pass
pilot_attack_output_acceptance_report.json: recommended_next_stage = ceg_detection_pilot
```

### P4: 运行 CEG detector 与内部消融

目标: 对 clean, watermarked 和 attacked 图像生成统一 detection events。

必须输出:

```text
ceg_detection/detection_events.json
ceg_detection/detection_thresholds.json
ceg_detection/ceg_detection_execution_manifest.json
ceg_detection/ablation_observations.json
```

### P4.5: detection 输出接收门禁

推荐命令:

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

完成门禁:

```text
pilot_detection_output_acceptance_report.json: overall_decision = pass
pilot_detection_output_acceptance_report.json: recommended_next_stage = fixed_fpr_statistics_pilot
```

### P5: 接入 external baseline

目标: 至少接入一个外部 baseline, 最终扩展到论文计划中的全部 baseline。

目标 baseline:

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

必须输出:

```text
external_baselines/baseline_observations.json
external_baselines/baseline_execution_manifest.json
external_baselines/external_result_evidence_report.json
```

### P5.5: external baseline 输出接收门禁

推荐命令:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline 声明应使用:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-formal-evidence --require-pass
```

完成门禁:

```text
pilot_baseline_output_acceptance_report.json: overall_decision = pass
pilot_baseline_output_acceptance_report.json: recommended_next_stage = quality_metric_pilot
```

### P6: 接入质量指标

目标: 补充图像质量和文本一致性指标, 避免论文只报告检测性能。

建议指标:

```text
PSNR
SSIM
LPIPS
FID
CLIP score
bit accuracy
payload recovery rate
```

必须输出:

```text
external_metrics/metric_rows.json
external_metrics/metric_execution_manifest.json
external_metrics/quality_metric_summary_table.csv
```

### P6.5: quality metric 输出接收门禁

目标: 验证 metric rows 与 metric manifest 是否可进入论文质量指标表和结果包。

计划命令:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric 声明应要求 evidence:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-formal-evidence --require-pass
```

该门禁当前已经具备实现、CLI 和测试。当前 MyDrive 工作区报告为 `fail`, 原因是 `external_metrics/metric_rows.json` 与 `external_metrics/metric_execution_manifest.json` 尚未由真实 metric backend 或离线导入器写出。

### P7: 统计 TPR@FPR 与论文表格

目标: 使用与 `D:/Code/CEG-WM` 对齐的 fixed-FPR 统计口径生成论文表格。

TPR@FPR 统计口径:

1. 使用 calibration clean negative 分数选择 `threshold_at_fpr`。
2. 使用 test clean negative 分数复核 `test_fpr_at_threshold`。
3. 使用 test positive 分数计算 clean 或 watermarked `TPR@FPR`。
4. 使用 attacked positive 分数按 `attack_family` 和 `attack_condition` 计算 attack `TPR@FPR`。
5. threshold 选择不得使用 test split。
6. 所有论文表格必须从 records 和 manifests 重建, 不能手工拼表。

必须输出:

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
baseline_comparison_table.csv
statistical_test_report.json
```

### P7.5: fixed-FPR / TPR@FPR 统计输出接收门禁

目标: 验证 fixed-FPR threshold 表、TPR@FPR 表、attack TPR 表和 baseline comparison 表是否满足论文主表与结果包构建的最小契约。

推荐命令:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root {workspace}/paper_outputs/artifacts --out {workspace}/pilot_fixed_fpr_output_acceptance_report.json --require-pass
```

正式论文统计检验声明应使用:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root {workspace}/paper_outputs/artifacts --out {workspace}/pilot_fixed_fpr_output_acceptance_report.json --require-statistical-report --require-pass
```

完成门禁:

```text
pilot_fixed_fpr_output_acceptance_report.json: overall_decision = pass
pilot_fixed_fpr_output_acceptance_report.json: recommended_next_stage = paper_result_package_pilot
```

该门禁当前已经具备实现、CLI 和测试。当前 MyDrive 工作区报告为 `fail`, 原因是 `paper_outputs/artifacts` 下尚未由真实 records 重建 fixed-FPR / TPR@FPR 统计表。

### P8: 构建论文结果包

目标: 形成可供论文撰写和发表使用的结果包。

必须包含:

1. prompt / split / seed / model / watermark 配置。
2. clean / watermarked / attacked 图像或可复核索引。
3. 图像生成, attack, detection, baseline, metric 的 manifests。
4. fixed-FPR / TPR@FPR / attack TPR / baseline comparison 表格。
5. `image_example_manifest.json` 和示例水印图像。
6. `paper_results_report.md`。
7. `paper_readiness_report.json`。
8. `paper_claim_audit.json`。
9. `paper_result_evidence_report.json`。
10. `external_result_evidence_report.json`。
11. `paper_results_package_manifest.json`。
12. MyDrive 归档 zip 和 package manifest。

### P8.5: paper_results_package 输出接收门禁

目标: 在 MyDrive 归档前验证 `paper_results_package` 是否包含 records、论文主表、图表 manifest、LaTeX 表、PDF 图、readiness、claim audit 和 package manifest。

推荐命令:

```text
python scripts/validate_pilot_paper_results_package.py --package-root {workspace}/paper_results_package --out {workspace}/pilot_paper_results_package_acceptance_report.json --require-pass
```

正式论文结果包应使用:

```text
python scripts/validate_pilot_paper_results_package.py --package-root {workspace}/paper_results_package --out {workspace}/pilot_paper_results_package_acceptance_report.json --require-evidence --require-image-examples --require-pass
```

完成门禁:

```text
pilot_paper_results_package_acceptance_report.json: overall_decision = pass
pilot_paper_results_package_acceptance_report.json: recommended_next_stage = mydrive_archive_pilot
```

该门禁当前已经具备实现、CLI 和测试。当前 MyDrive 工作区报告预计为 `fail`, 原因是 `paper_results_package` 尚未由真实 records 和 manifests 导出。

### P8.6: MyDrive 归档输出接收门禁

目标: 在论文写作使用前验证 MyDrive 分类归档是否同时包含目录快照、zip 包和 archive manifest, 且三者文件列表和摘要一致。

推荐命令:

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --out {workspace}/pilot_mydrive_archive_acceptance_report.json --require-pass
```

若需要校验指定 run_id:

```text
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --run-id <run_id> --out {workspace}/pilot_mydrive_archive_acceptance_report.json --require-pass
```

完成门禁:

```text
pilot_mydrive_archive_acceptance_report.json: overall_decision = pass
pilot_mydrive_archive_acceptance_report.json: recommended_next_stage = paper_writing_ready_pilot
```

该门禁当前已经具备实现、CLI 和测试。当前 MyDrive 归档根目录尚未包含真实 paper_results_package 归档, 因此报告应正确阻断。

### P9: pilot 阶段进度汇总

目标: 把真实 pilot 工作区内所有阶段门禁报告汇总为 JSON 和 Markdown, 直接指出首个阻断阶段和下一步行动。

推荐命令:

```text
python scripts/build_pilot_stage_progress_summary.py --workspace {workspace}
```

输出:

```text
{workspace}/pilot_stage_progress_summary.json
{workspace}/pilot_stage_progress_summary.md
```

该汇总不替代任何门禁, 只负责把当前真实执行状态变成可读的推进看板。

## 8. 当前最短执行顺序

```text
S1. 打开 D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_plan_replacement_checklist.md, 逐项确认需要填写的真实值。
S2. 运行 build_pilot_input_value_pack_status.py, 生成 value pack 填写状态报告。
S3. 在 D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_input_value_pack.draft.json 中填写每项 value。
S4. value pack 状态报告通过后, 运行 apply_pilot_input_value_pack.py --require-pass。
S5. 运行 validate_pilot_input_plan_templates.py --require-pass。
S6. 运行 build_pilot_execution_readiness_report.py --require-pass。
S7. 填写 pilot_image_generation_launch_variables.draft.json。
S8. 运行 build_pilot_image_generation_launch_plan.py --require-pass。
S9. S8 通过后, 执行真实图像生成 backend。
S10. 图像生成完成后, 运行 validate_pilot_image_generation_outputs.py --require-pass。
S11. 图像接收门禁通过后, 执行 attack pilot。
S12. attack 完成后, 运行 validate_pilot_attack_outputs.py --require-pass。
S13. attack 接收门禁通过后, 运行 CEG detection。
S14. detection 完成后, 运行 validate_pilot_detection_outputs.py --require-pass。
S15. detection 接收门禁通过后, 运行 external baseline。
S16. baseline 完成后, 运行 validate_pilot_baseline_outputs.py --require-pass。
S17. baseline 接收门禁通过后, 运行 quality metric。
S18. metric 完成后, 运行 validate_pilot_metric_outputs.py --require-pass。
S19. metric 接收门禁通过后, 运行 fixed-FPR / TPR@FPR 统计。
S20. 统计完成后, 运行 validate_pilot_fixed_fpr_outputs.py --require-pass。
S21. fixed-FPR 统计接收门禁通过后, 构建 paper_results_package。
S22. 运行 validate_pilot_paper_results_package.py --require-pass；正式论文结果包还应启用 --require-evidence 和 --require-image-examples。
S23. paper_results_package 接收门禁通过后, 归档到 MyDrive。
S24. 运行 validate_pilot_mydrive_archive.py --require-pass, 确认 package_snapshots、package_archives 和 package_manifests 一致。
S25. 每完成一个阶段后运行 build_pilot_stage_progress_summary.py, 更新当前阻断点和下一步行动。
```

## 9. 与 CEG-WM 的核心机制对齐要求

后续 `CEG` 必须继续与 `D:/Code/CEG-WM` 保持以下核心方法机制一致:

1. prompt / split / shard / experiment plan 先行。
2. calibration clean negative 与 test evaluation 严格分离。
3. attack 是鲁棒性统计的独立阶段, 不并入图像生成阶段。
4. detection scores 进入统一 records。
5. external baseline 进入统一 observation 或 event schema。
6. fixed-FPR threshold table, TPR@FPR table 和 attack TPR table 由 records 重建。
7. paper package 只归档可追溯 artifacts, 不归档无 provenance 的手工结果。

## 10. 当前下一步建议

当前已补齐从 quality metric 到 MyDrive 归档的工程接收口径, 并新增 pilot 阶段进度汇总。下一步应根据 `pilot_stage_progress_summary.md` 指出的首个阻断点, 填充真实 pilot 输入并依次产出真实 image、attack、detection、baseline、metric 和 fixed-FPR 表格；随后导出并验收 paper_results_package, 再归档到 MyDrive。
