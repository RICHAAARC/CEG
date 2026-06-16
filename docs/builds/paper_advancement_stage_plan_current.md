# CEG 当前向论文发表推进阶段计划快照

## 1. 文档定位

本文档是 `paper_publication_execution_stage_plan.md` 的当前执行摘要, 用于快速回答“下一步如何向论文推进”。整理日期为 2026-06-17。

本文档不声明 `CEG` 已经完成正式论文实验。当前项目已经完成若干工程门禁和真实 pilot 输入工作区脚手架, 但尚未完成真实 SD / watermark / attack / CEG detector / external baseline / advanced quality metric 的论文级运行。因此当前产物只能支撑工程 rehearsal、真实 pilot 输入准备和后续小规模 pilot, 不能直接支撑正式论文结论。

## 2. 当前阶段名称

```text
real_pilot_input_preparation
```

该阶段的含义是: 已经从 rehearsal package 和 readiness checklist 推进到真实 pilot 输入工作区准备阶段, 下一步应先完成 prompt、split、seed、model、watermark 等真实输入配置的占位字段替换与 preflight 校验, 再启动真实图像生成和检测流程。

该阶段名称属于 `CEG` 项目的治理语义, 不是通用机器学习项目必须使用的阶段名。通用工程写法是“先冻结输入契约, 再执行昂贵实验”; 项目特定写法是通过 `pilot_input_manifest`、`pilot_readiness_checklist`、MyDrive 分类目录和后续 preflight 报告把该过程固化为可审计门禁。

## 3. 当前已经完成的工程事实

### 3.1 rehearsal 输入覆盖补齐

已完成 rehearsal package 对核心字段的补齐。当前 rehearsal gap 中 `missing_core_fields` 已为空, 说明 `detection_execution_manifest` 和 `experiment_matrix` 这类核心输入已经具备 rehearsal 级覆盖。

代表性产物位置:

```text
D:\content\drive\MyDrive\CEG\pilot_rehearsals\pilot_rehearsal_20260617_032133
```

代表性结论:

```text
missing_core_fields = []
pilot_readiness_decision = rehearsal_or_partial_pilot_only
dry_run_marker_count = 6
formal_claim_gap_count = 3
```

该结论的含义是: rehearsal 链路的字段覆盖已经补齐, 但仍存在 dry-run 标记和正式声明缺口, 因此不能直接进入正式论文实验。

### 3.2 pilot readiness checklist 门禁

已建立并运行 `pilot_readiness_checklist` 门禁, 将 gap 报告转换为真实 pilot 启动前必须补齐的清单。

代表性产物位置:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\pilot_readiness_inputs_20260617_032133\pilot_readiness_checklist.json
D:\content\drive\MyDrive\CEG\pilot_runs\pilot_readiness_inputs_20260617_032133\pilot_readiness_checklist.md
```

代表性结论:

```text
overall_decision = not_ready_for_formal_pilot
recommended_next_stage = real_pilot_input_preparation
blocking_item_count = 6
```

该结论的含义是: 当前可以继续准备真实 pilot 输入, 但不能宣称已经具备正式 pilot 或正式论文实验条件。

### 3.3 真实 pilot 输入工作区脚手架

已建立真实 pilot 输入工作区脚手架, 用于统一放置后续真实 SD、水印图像、攻击图像、检测结果、baseline 输出、quality metric 输出和实验计划。

代表性产物位置:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500
```

关键文件包括:

```text
pilot_input_manifest.draft.json
pilot_run_workspace_manifest.json
README.md
```

### 3.4 真实 pilot 输入计划模板

已在真实 pilot 输入工作区中生成 prompt、split、seed、model 和 watermark 配置草稿。

关键文件包括:

```text
inputs\prompts\prompt_plan.draft.json
inputs\prompts\split_plan.draft.json
inputs\prompts\seed_plan.draft.json
configs\model_config.draft.json
configs\watermark_config.draft.json
pilot_input_plan_template_manifest.json
```

这些文件当前仍是草稿模板。凡是字段名以 `_placeholder` 结尾, 或字段值仍包含替换提示的内容, 都必须在启动真实 SD / watermark 前替换为真实实验配置。

## 4. 当前不能宣称的事项

```text
1. 不能宣称已经完成真实 SD 图像生成正式实验。
2. 不能宣称已经完成真实 watermark backend 正式实验。
3. 不能宣称已经完成真实 attack 全流程实验。
4. 不能宣称已经完成真实 CEG detector 全量分数。
5. 不能宣称已经完成真实 external baseline 对比。
6. 不能宣称已经完成 LPIPS / FID / CLIP score 等正式高级指标。
7. 不能把 rehearsal 或 dry-run 数值写成论文性能结论。
8. 不能把仍含 `_placeholder` 字段的配置作为真实 pilot 输入。
```

## 5. 下一步最短推进路径

当前最短路径应从“模板是否可运行”推进到“小规模真实 pilot 是否可复核”。建议顺序如下:

```text
D0: 对真实 pilot 输入计划模板运行 preflight, 检查 prompt、split、seed、model、watermark 配置是否仍含 `_placeholder` 字段。
D1: 将 prompt_plan.draft.json 替换为真实 prompt 集, 明确 prompt_id、prompt_text、prompt_source、split 和用途。
D2: 将 split_plan.draft.json 替换为 calibration / test 划分, 明确 clean negative、positive、attacked positive 的角色。
D3: 将 seed_plan.draft.json 替换为真实 seed 列表, 固化可复现实验随机性。
D4: 将 model_config.draft.json 替换为真实 SD 或外部生成 backend 配置, 明确 model_id、scheduler、resolution、precision、device 和证据路径。
D5: 将 watermark_config.draft.json 替换为真实 watermark 方法配置, 明确 payload、strength、backend、输出路径和证据路径。
D6: 生成小规模 clean / watermarked 图像, 并写出 image_generation_manifest.json 与 image_pair_manifest.json。
D7: 对 watermarked 图像执行最小 attack 集合, 写出 attacked_image_manifest.json 与 attack_shard_manifest.json。
D8: 运行 CEG detector 小样本 pilot, 写出 detection_events.json、detection_thresholds.json 和 ceg_detection_execution_manifest.json。
D9: 接入至少一个 external baseline, 写出 baseline_observations.json 和 baseline_execution_manifest.json。
D10: 接入至少一种高级或正式质量指标, 写出 metric_rows.json 和 metric_execution_manifest.json。
D11: 运行 fixed-FPR / TPR@FPR 统计, 构建 paper_results_package pilot 并归档到 MyDrive。
D12: 基于 pilot gap、readiness、claim audit 和 evidence report 决定是否冻结正式实验配置。
```

## 6. attack 的流程位置

`attack` 是论文结果流程的必须阶段, 但不应并入图像生成阶段。推荐边界如下:

```text
图像生成阶段: 负责 prompt -> clean image / watermarked image。
attack 阶段: 负责 watermarked image -> attacked image, 并记录 attack_family、attack_condition 和 attack_params。
detection 阶段: 同时消费 clean、watermarked 和 attacked 图像, 输出统一 detection events。
统计阶段: 基于 detection events 计算 clean TPR@FPR、attack TPR@FPR 和鲁棒性表格。
```

这样划分的主要原因是: attack 改变的是测试条件, 不是水印生成方法本身。将 attack 独立成阶段可以避免把“生成质量问题”“攻击鲁棒性问题”和“检测器阈值问题”混在一起。

## 7. TPR@FPR 统计口径

`CEG` 应按照与 `CEG-WM` 对齐的 fixed-FPR 口径统计 TPR@FPR:

```text
1. 使用 calibration clean negative 分数选择 threshold_at_fpr。
2. 使用 test clean negative 分数复核 test_fpr_at_threshold。
3. 使用 test positive 分数计算 clean 或 watermarked TPR@FPR。
4. 使用 attacked positive 分数按 attack_family 和 attack_condition 计算 attack TPR@FPR。
5. 阈值选择不得使用 test split。
6. 论文表格必须由 detection events、threshold records 和统计 manifests 重建。
```

该口径中的“阈值校准和测试评估分离”属于通用统计工程原则; 通过 manifest、records 和 paper package builder 固化该口径属于本项目特定实现。

## 8. 论文结果包必须包含的产物

论文发表结果包最终至少应包含:

```text
1. prompt / split / seed / model / watermark 配置。
2. clean 图像、watermarked 图像和 attacked 图像, 或对应可复核 manifest 与归档索引。
3. image_generation_manifest.json、image_pair_manifest.json、attacked_image_manifest.json。
4. detection_events.json、detection_thresholds.json、ceg_detection_execution_manifest.json。
5. baseline_observations.json、baseline_execution_manifest.json。
6. metric_rows.json、metric_execution_manifest.json。
7. fixed_fpr_threshold_table.csv。
8. tpr_at_fixed_fpr_table.csv。
9. attack_tpr_at_fixed_fpr_table.csv。
10. baseline_comparison_table.csv。
11. image_example_manifest.json 和示例水印图像。
12. paper_results_report.md。
13. paper_readiness_report.json。
14. paper_claim_audit.json。
15. paper_result_evidence_report.json。
16. external_result_evidence_report.json。
17. paper_results_package_manifest.json。
18. MyDrive 归档 zip 与 package manifest。
```

其中水印图像不是可选项。若论文需要展示方法效果、攻击鲁棒性和图像质量, 结果包必须能产出示例 watermarked images、attacked images 和 comparison grids。可以不把所有全量图片写入论文正文, 但结果包中必须保留足够示例图和可追溯 manifest。

## 9. MyDrive 落盘规则

所有可供复核的运行结果应同步保存到:

```text
D:\content\drive\MyDrive\CEG
```

在 Colab 环境中对应路径为:

```text
/content/drive/MyDrive/CEG
```

推荐分类目录如下:

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

## 10. 不可跳过的门禁

### 10.1 真实 pilot 输入计划 preflight

当前已经建立真实 pilot 输入计划 preflight 门禁。该门禁只检查 prompt、split、seed、model 和 watermark 配置草稿是否仍含 `_placeholder` 字段或替换提示, 不运行真实 SD、watermark、attack 或 detector。推荐命令如下:

```text
python scripts/validate_pilot_input_plan_templates.py --workspace D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --out D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_preflight_report.json
```

如果要把它作为真实运行前的硬门禁, 应加入 `--require-pass`。当报告为 `fail` 时, 下一步不是运行 SD, 而是替换所有占位字段并重新预检。

为避免人工从 preflight JSON 中逐项查找字段, 当前还应生成替换清单:

```text
python scripts/build_pilot_input_replacement_checklist.py --preflight-report D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_preflight_report.json --out-json D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_replacement_checklist.json --out-md D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_replacement_checklist.md
```

该清单把每个 `_placeholder` 字段映射为应写入的正式字段名和内容要求, 例如 `prompt_text_placeholder -> prompt_text`、`model_id_placeholder -> model_id`、`watermark_method_placeholder -> watermark_method`。

为减少同时编辑多个计划文件的风险, 应先生成集中填写的值包草稿:

```text
python scripts/scaffold_pilot_input_value_pack.py --replacement-checklist D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_plan_replacement_checklist.json --out D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack.draft.json
```

填写值包中每一项的 `value` 字段后, 再应用到工作区计划文件:

```text
python scripts/apply_pilot_input_value_pack.py --workspace D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --value-pack D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack.draft.json --require-pass
python scripts/validate_pilot_input_plan_templates.py --workspace D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --require-pass
```

值包草稿仍含 `value_placeholder` 时, 应用报告必须为 `fail`, 这表示当前仍处于真实输入准备阶段。

在尝试启动真实图像生成前, 应再生成聚合就绪报告:

```text
python scripts/build_pilot_execution_readiness_report.py --workspace D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500 --require-pass
```

该报告要求 `pilot_input_plan_preflight_report.json` 和 `pilot_input_value_pack_application_report.json` 同时为 `pass`。如果任一报告为 `fail`, 当前仍不能启动真实 SD / watermark。

```text
pilot_input_plan_preflight_report.json
pilot_input_gap_report.json
pilot_readiness_checklist.json
external_result_evidence_report.json
paper_result_evidence_report.json
paper_readiness_report.json
paper_claim_audit.json
colab_acceptance_report.json
```

如果 `pilot_input_plan_preflight_report.json` 显示仍存在 `_placeholder` 字段, 则不能启动真实 SD / watermark 运行。如果 `pilot_input_gap_report.json` 仍为 `rehearsal_or_partial_pilot_only`, 则当前产物只能用于工程 rehearsal 或 partial pilot, 不能作为正式论文结果声明。

## 11. 与 D:\Code\CEG-WM 的方法机制对齐要求

后续 `CEG` 应继续与 `CEG-WM` 保持以下核心机制一致:

```text
1. prompt / split / shard / experiment plan 先行。
2. clean negative calibration 与 test evaluation 分离。
3. attack 是鲁棒性统计的独立阶段, 不并入图像生成阶段。
4. detection scores 进入统一 records。
5. external baseline 进入统一 observation 或 event schema。
6. fixed-FPR threshold table、TPR@FPR table 和 attack TPR table 由 records 重建。
7. paper package 只归档可追溯 artifacts, 不归档无 provenance 的手工结果。
```

如后续实现发现 `CEG` 与 `CEG-WM` 在核心算法原语、split 语义、threshold 校准或 attack grouping 上出现偏离, 应优先修正 `CEG` 的工程实现或在文档中明确说明差异, 不能静默生成不可比结果。
