# CEG 当前向论文发表推进阶段计划快照

## 1. 文档定位

本文档落盘于 `D:/Code/CEG/docs/builds`，用于把当前阶段计划整理为可执行的论文推进路线。整理日期为 2026-06-17。

本文档不声明 `CEG` 已经完成正式论文实验。当前项目已经建立工程治理、真实 pilot 输入工作区、输入预检、替换清单、值包、执行就绪报告和图像生成启动计划门禁，但真实 SD / watermark / attack / CEG detector / external baseline / advanced quality metric 尚未完成论文级运行。因此，当前阶段的核心任务不是撰写最终结果，而是把真实 pilot 从“输入准备”推进到“可复核的小规模结果包”。

## 2. 当前阶段名称

```text
real_pilot_input_preparation
```

该阶段的含义是：真实 pilot 工作区已经创建，但关键输入配置仍包含占位内容。下一步必须先补齐真实 prompt、split、seed、model、watermark 和图像生成输出位置，再通过门禁，才能启动真实图像生成。

该阶段名称属于本项目的治理语义。通用工程写法是“先冻结实验输入，再运行小规模实验”；本项目的特殊设计是把这个过程拆成 preflight、replacement checklist、value pack、execution readiness 和 launch plan 等可审计产物。

## 3. 当前真实状态快照

### 3.1 MyDrive 工作区

当前真实 pilot 工作区为：

```text
D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500
```

该目录属于论文推进过程中的运行产物区，不是 Git 仓库内正式源码目录。

### 3.2 已经存在的关键产物

```text
pilot_input_manifest.draft.json
pilot_run_workspace_manifest.json
README.md
inputs\prompts\prompt_plan.draft.json
inputs\prompts\split_plan.draft.json
inputs\prompts\seed_plan.draft.json
configs\model_config.draft.json
configs\watermark_config.draft.json
pilot_input_plan_template_manifest.json
pilot_input_plan_preflight_report.json
pilot_input_plan_replacement_checklist.json
pilot_input_plan_replacement_checklist.md
pilot_input_value_pack.draft.json
pilot_input_value_pack_application_report.json
pilot_execution_readiness_report.json
pilot_image_generation_launch_variables.draft.json
pilot_image_generation_launch_plan_report.json
```

### 3.3 当前门禁结论

| 门禁产物 | 当前结论 | 下一阶段建议 | 关键含义 |
|---|---:|---|---|
| `pilot_input_plan_preflight_report.json` | `fail` | `replace_pilot_input_plan_placeholders` | 仍有 36 个占位发现，不能启动真实 SD / watermark。 |
| `pilot_input_plan_replacement_checklist.json` | `fail` | `rerun_pilot_input_plan_preflight` | 已整理出 19 个替换任务。 |
| `pilot_input_value_pack_application_report.json` | `fail` | `fill_missing_real_values_in_value_pack` | 值包尚未填入真实 `value`，0 个任务被应用，19 个任务阻断。 |
| `pilot_execution_readiness_report.json` | `fail` | `complete_value_pack_and_rerun_preflight` | 聚合就绪门禁未通过，有 2 个严格门禁阻断。 |
| `pilot_image_generation_launch_plan_report.json` | `fail` | `complete_execution_readiness_and_launch_variables` | 图像生成启动计划尚无可执行命令，仍有 3 个阻断项。 |

## 4. 当前不能宣称的事项

```text
1. 不能宣称已经完成真实 SD 图像生成正式实验。
2. 不能宣称已经完成真实 watermark backend 正式实验。
3. 不能宣称已经完成真实 attack 全流程实验。
4. 不能宣称已经完成真实 CEG detector 全量评分。
5. 不能宣称已经完成 external baseline 对比。
6. 不能宣称已经完成 LPIPS / FID / CLIP score 等正式高级质量指标。
7. 不能把 rehearsal、dry-run 或 mock 数值写成论文性能结论。
8. 不能把仍含 `_placeholder` 字段的配置作为真实 pilot 输入。
```

## 5. 向论文推进的阶段计划

### 阶段 P0：补齐真实 pilot 输入

目标：把所有 `.draft.json` 中的占位字段替换为真实实验配置。

必须完成：

```text
1. 在 `pilot_input_value_pack.draft.json` 中为 19 个替换任务填写真实 `value`。
2. 应用值包到 prompt / split / seed / model / watermark 计划文件。
3. 重新运行输入 preflight，并要求通过。
4. 重新运行 execution readiness，并要求通过。
```

推荐命令：

```text
python scripts/apply_pilot_input_value_pack.py --workspace D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --value-pack D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack.draft.json --require-pass
python scripts/validate_pilot_input_plan_templates.py --workspace D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_preflight_report.json --require-pass
python scripts/build_pilot_execution_readiness_report.py --workspace D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_execution_readiness_report.json --require-pass
```

完成门禁：

```text
pilot_input_plan_preflight_report.json: overall_decision = pass
pilot_input_value_pack_application_report.json: overall_decision = pass
pilot_execution_readiness_report.json: overall_decision = pass
```

### 阶段 P1：生成真实图像生成启动计划

目标：将真实输入配置转换为外部图像生成 backend 可消费的命令计划。

必须完成：

```text
1. 填写 `pilot_image_generation_launch_variables.draft.json` 中的真实图像输出根目录、backend 参数和资源信息。
2. 重新生成 `pilot_image_generation_launch_plan_report.json`。
3. 要求 command_plan 非空，并且所有阻断项为 0。
```

推荐命令：

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_image_generation_launch_plan_report.json --require-pass
```

完成门禁：

```text
pilot_image_generation_launch_plan_report.json: overall_decision = pass
pilot_image_generation_launch_plan_report.json: command_count > 0
```

### 阶段 P2：运行真实图像生成与水印生成

目标：执行真实 SD / watermark backend，产出 clean / watermarked 图像和图像级 manifest。

必须输出：

```text
inputs\images\prompt_plan.json
inputs\images\image_pairs.json
inputs\images\image_manifests\image_generation_manifest.json
inputs\images\image_manifests\image_pair_manifest.json
inputs\images\clean\*
inputs\images\watermarked\*
```

完成门禁：

```text
1. 每个 `image_pairs.json` 记录都能追溯 clean_image_path 和 watermarked_image_path。
2. 所有图像路径真实存在。
3. 图像生成 manifest 与 pair manifest 的样本数一致或有明确解释。
4. 输出仍然保存到 MyDrive 运行目录，不写入 Git 仓库 `outputs/`。
```

### 阶段 P3：执行 attack pilot

目标：基于 watermarked 图像执行最小 attack 集合，测试鲁棒性。

attack 是论文流程必须项，但不应并入图像生成阶段。推荐边界如下：

```text
图像生成阶段: prompt -> clean image / watermarked image
attack 阶段: watermarked image -> attacked image
检测阶段: clean / watermarked / attacked image -> detection events
统计阶段: detection events -> fixed-FPR / TPR@FPR 表格
```

必须输出：

```text
attacked_image_manifest.json
attack_shard_manifest.json
attack_execution_manifest.json
attacked images
```

完成门禁：每个 attacked image 必须记录 `attack_family`、`attack_condition`、`attack_params` 和源 watermarked 图像。

### 阶段 P4：运行 CEG detector 与内部消融

目标：对 clean、watermarked 和 attacked 图像生成统一 detection events。

必须输出：

```text
detection_events.json
detection_thresholds.json
ceg_detection_execution_manifest.json
ablation_observations.json
```

完成门禁：所有分数记录必须包含 split、sample_id、label、score、method、source_image、run_id 和 provenance。

### 阶段 P5：接入 external baseline

目标：加入至少一个外部 baseline，形成论文对比。

必须输出：

```text
baseline_observations.json
baseline_execution_manifest.json
external_result_evidence_report.json
```

完成门禁：baseline 的输入样本、阈值选择、检测事件、统计口径必须与 CEG 对齐；若外部方法无法完全对齐，必须在 evidence report 中显式说明差异。

### 阶段 P6：接入质量指标

目标：补充图像质量和文本一致性评价，避免论文只报告检测性能。

建议指标：

```text
LPIPS
FID
CLIP score
可选的人类可视化示例图 manifest
```

必须输出：

```text
metric_rows.json
metric_execution_manifest.json
quality_metric_summary_table.csv
```

### 阶段 P7：统计 TPR@FPR 与论文表格

目标：使用与 `D:/Code/CEG-WM` 对齐的 fixed-FPR 统计口径生成论文表格。

统计口径：

```text
1. 用 calibration clean negative 分数选择 threshold_at_fpr。
2. 用 test clean negative 分数复核 test_fpr_at_threshold。
3. 用 test positive 分数计算 clean 或 watermarked TPR@FPR。
4. 用 attacked positive 分数按 attack_family 和 attack_condition 计算 attack TPR@FPR。
5. threshold 选择不得使用 test split。
6. 所有论文表格必须从 records 和 manifests 重建，不能手工拼表。
```

必须输出：

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
baseline_comparison_table.csv
statistical_test_report.json
```

### 阶段 P8：构建论文结果包

目标：形成可供论文撰写和发表使用的结果包。

必须包含：

```text
1. prompt / split / seed / model / watermark 配置。
2. clean / watermarked / attacked 图像或可复核索引。
3. 图像生成、attack、detection、baseline、metric 的 manifests。
4. fixed-FPR / TPR@FPR / attack TPR / baseline comparison 表格。
5. image_example_manifest.json 和示例水印图像。
6. paper_results_report.md。
7. paper_readiness_report.json。
8. paper_claim_audit.json。
9. paper_result_evidence_report.json。
10. external_result_evidence_report.json。
11. paper_results_package_manifest.json。
12. MyDrive 归档 zip 和 package manifest。
```

## 6. 下一步最短执行顺序

当前最短路径不是运行模型，而是补齐值包。建议严格按以下顺序推进：

```text
S1. 打开 `D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_replacement_checklist.md`，逐项确认 19 个需要填写的真实值。
S2. 在 `D:/content/drive/MyDrive/CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack.draft.json` 中填写每项 `value`。
S3. 运行 `apply_pilot_input_value_pack.py --require-pass`。
S4. 运行 `validate_pilot_input_plan_templates.py --require-pass`。
S5. 运行 `build_pilot_execution_readiness_report.py --require-pass`。
S6. 填写 `pilot_image_generation_launch_variables.draft.json`。
S7. 运行 `build_pilot_image_generation_launch_plan.py --require-pass`。
S8. 只有在 S7 通过后，才执行真实图像生成 backend。
S9. 图像生成输出通过接收门禁后，再进入 attack pilot。
S10. attack、detection、baseline、quality metric 和 fixed-FPR 统计依次执行。
```

## 7. MyDrive 落盘规则

所有运行结果应保存到：

```text
D:/content/drive/MyDrive/CEG
```

在 Colab 中对应路径为：

```text
/content/drive/MyDrive/CEG
```

推荐子目录：

```text
pilot_rehearsals/        保存 rehearsal package 快照
pilot_runs/              保存真实或半真实 pilot 结果
package_snapshots/       保存展开后的 paper_results_package
package_archives/        保存 zip 归档包
package_manifests/       保存归档索引 manifest
change_reports/          保存工程变更说明
schedule_reports/        保存阶段计划与排期快照
audit_reports/           保存 pytest、harness、readiness、claim、gap 等审计报告
external_evidence/       保存 external baseline 和 advanced metric 证据报告
formal_runs/             保存正式论文实验输出
```

## 8. 与 D:/Code/CEG-WM 的方法机制对齐要求

后续 `CEG` 必须与 `CEG-WM` 保持以下核心机制一致：

```text
1. prompt / split / shard / experiment plan 先行。
2. calibration clean negative 与 test evaluation 分离。
3. attack 作为鲁棒性统计的独立阶段，不并入图像生成阶段。
4. detection scores 进入统一 records。
5. external baseline 进入统一 observation 或 event schema。
6. fixed-FPR threshold table、TPR@FPR table 和 attack TPR table 由 records 重建。
7. paper package 只归档可追溯 artifacts，不归档无 provenance 的手工结果。
```

如果后续实现发现 `CEG` 与 `CEG-WM` 在核心算法原语、split 语义、threshold 校准或 attack grouping 上出现偏离，应优先修正 `CEG` 的工程实现，或在文档中明确说明差异，不能静默生成不可比结果。

## 9. 当前阶段判定

```text
当前状态: 未达到真实图像生成启动条件
当前阻断: 真实输入值包未填写, 输入 preflight 未通过, execution readiness 未通过, 图像生成 launch plan 未通过
下一步: 填写并应用 pilot_input_value_pack.draft.json 中的真实 value
可以做: 补齐真实输入、重跑门禁、整理运行证据
不应做: 直接运行 SD / watermark / attack / detection / baseline 并把结果当作论文结论
```
