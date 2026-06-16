# CEG 当前向论文发表推进阶段计划快照

## 1. 文档定位

本文档是 `paper_publication_execution_stage_plan.md` 的当前执行摘要, 用于快速回答“下一步如何向论文推进”。整理日期为 2026-06-17。

本文档不声明 `CEG` 已经完成正式论文实验。当前应先完成 pilot 输入门禁、外部证据门禁和结果包可重建门禁, 再启动真实 pilot 与正式实验。

## 2. 当前阶段

```text
pilot_input_and_external_evidence_gate_completion
```

该阶段的核心目标是: 在真实 SD / watermark / attack / CEG detector / external baseline / advanced quality metric 大规模运行前, 先让所有输入、证据、统计口径、结果包归档和审计报告可被复核。

## 3. 立即执行计划

```text
1. 补齐 rehearsal package 中的 detection_execution_manifest 和 experiment_matrix。
2. 重新生成 rehearsal package。
3. 重新运行 pilot_input_gap_report。
4. 确认 missing_core_fields 不再包含 detection_execution_manifest / experiment_matrix。
5. 运行 scripts/build_pilot_readiness_checklist.py, 将 gap 报告转换为真实 pilot 启动清单。
6. 准备小规模真实 pilot 输入。
7. 运行真实 CEG detector pilot。
8. 接入至少一个 external baseline。
9. 接入至少一种 advanced quality metric。
10. 统计 fixed-FPR / TPR@FPR。
11. 构建并归档 paper_results_package。
```

## 4. 结果落盘目录

Windows 本地路径:

```text
D:\content\drive\MyDrive\CEG
```

Colab 路径:

```text
/content/drive/MyDrive/CEG
```

推荐子目录:

```text
pilot_rehearsals/
pilot_runs/
package_snapshots/
package_archives/
package_manifests/
change_reports/
schedule_reports/
audit_reports/
external_evidence/
formal_runs/
```

## 5. 不可跳过的门禁

```text
pilot_input_gap_report.json
pilot_readiness_checklist.json
external_result_evidence_report.json
paper_result_evidence_report.json
paper_readiness_report.json
paper_claim_audit.json
```

如果 `pilot_input_gap_report.json` 仍为 `rehearsal_or_partial_pilot_only`, 则当前产物只能用于工程 rehearsal 或 partial pilot, 不能作为正式论文结果声明。

---

## 真实 pilot 输入工作区脚手架

在生成 `pilot_readiness_checklist.json` 后, 应运行以下命令创建可填充的真实 pilot 输入工作区:

```text
python scripts/scaffold_pilot_run_workspace.py --checklist <pilot_readiness_checklist.json> --out <MyDrive>/pilot_runs/<run_id> --run-id <run_id>
python scripts/scaffold_pilot_input_plan_templates.py --workspace <MyDrive>/pilot_runs/<run_id> --run-id <run_id>
```

第一条命令只创建目录、`pilot_input_manifest.draft.json`、`pilot_run_workspace_manifest.json` 和 README。第二条命令写出 prompt、split、seed、model 和 watermark 配置草稿。两者都不生成任何正式实验结果。其主要价值是把真实 SD / watermark / attack / detector / external baseline / advanced metric 输出放到统一位置, 便于后续运行 preflight、gap audit 和 paper package builder。

推荐填充顺序如下:

```text
1. inputs/prompts/ 先生成 prompt_plan.draft.json、split_plan.draft.json 和 seed_plan.draft.json, 再替换其中的 *_placeholder 字段。
2. inputs/images/clean/ 写入真实 clean 图像。
3. inputs/images/watermarked/ 写入真实 watermarked 图像。
4. inputs/image_pairs.json 绑定 prompt、seed、clean 图像和 watermarked 图像。
5. image_attacks/image_manifests/ 写入 attacked_image_manifest.json 和 attack_shard_manifest.json。
6. ceg_detection/ 写入 detection_events.json、detection_thresholds.json 和 ceg_detection_execution_manifest.json。
7. external_baselines/ 写入 baseline_observations.json 和 baseline_execution_manifest.json。
8. external_metrics/ 写入 metric_rows.json 和 metric_execution_manifest.json。
9. plans/ 写入 paper_experiment_matrix.json。
10. configs/ 写入 paper_output_requirements.json, 并替换 model_config.draft.json 与 watermark_config.draft.json 中的 *_placeholder 字段。
```

如果工作区仍只有草稿 manifest 或空目录, 只能说明真实 pilot 输入位置已经准备好, 不能说明论文实验已经完成。
