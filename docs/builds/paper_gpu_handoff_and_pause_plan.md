# CEG 论文结果包 GPU 交接与暂停计划

## 1. 文档定位

本文档保存于 `D:\Code\CEG\docs\builds\paper_gpu_handoff_and_pause_plan.md`。它用于落实当前目标中的关键约束:

```text
本地没有 GPU 环境。结果包需要真实 GPU 环境测试跑出时需要暂停并让我进行真实 GPU 环境测试。
```

本文档不是实验结果报告, 也不是 GPU 运行脚本本体。它的作用是把本地可继续推进的工程工作、必须暂停交给真实 GPU 环境执行的工作、GPU 执行后必须交回的产物、以及重新接入 `D:\Code\CEG` 的验收命令整理成一个可审计交接计划。

整理日期: `2026-06-17`

---

## 2. 当前真实状态

当前项目仍处于:

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

当前阻断原因是:

```text
pilot_input_value_pack_fill_sheet.csv 中 19 个 value_json 仍未填写。
```

因此, 当前还没有进入 GPU 运行阶段。当前必须先由人工或上游系统补齐真实输入值, 再运行只读预检和 P0 输入冻结门禁。

---

## 3. 本地可继续执行的工作

本地 CPU 环境可以继续执行以下工作。这些工作只验证工程契约、文件结构、manifest schema、命令链路和结果包治理规则, 不产生论文性能结论。

| 阶段 | 本地可执行事项 | 是否支持论文 claim |
|---|---|---:|
| P0 | 导出 value pack 填写表、导出填写指南、只读预检 CSV、导入 CSV、P0 dry-run | 否 |
| P1 | 生成 image generation launch variables 和 launch plan | 否 |
| P2 前 | 校验 image output acceptance 脚本是否能正确阻断缺失图像 | 否 |
| P3 前 | 校验 attack output acceptance 脚本是否能正确阻断缺失 attacked image | 否 |
| P4 前 | 校验 detection output acceptance 脚本是否能正确阻断缺失 detection events | 否 |
| P5 前 | 校验 baseline output acceptance 和 evidence gate | 否 |
| P6 前 | 校验 metric output acceptance 和 evidence gate | 否 |
| P7 前 | 校验 fixed-FPR 输出接收门禁 | 否 |
| P8 到 P10 前 | 校验 paper package、MyDrive archive、claim audit 和 readiness gate | 否 |

本地允许继续做的是“门禁、适配、预检、打包、文档和 dry-run”。本地禁止把 mock image、dry-run score 或 placeholder manifest 写成论文性能结果。

---

## 4. 必须暂停交给真实 GPU 环境执行的阶段

当 P0 和 P1 通过后, 以下阶段必须暂停本地推进, 由用户在真实 GPU / Colab / 外部 backend 环境执行。

| 暂停点 | 触发条件 | 需要 GPU 或真实外部 backend 的原因 | 用户执行后需要交回 |
|---|---|---|---|
| GPU-P2 | `pilot_image_generation_launch_plan_report.json` 为 `pass` 且 `command_count > 0` | 需要真实 SD 或等价图像生成 backend 产出 clean / watermarked 图像 | `inputs/images/clean/*`, `inputs/images/watermarked/*`, `image_pairs.json`, image manifests |
| GPU-P3 | P2 图像接收门禁通过 | 需要对真实 watermarked 图像执行 attack, 产出 attacked image | `image_attacks/attacked_images/*`, `image_pairs_attacked.json`, attack manifests |
| GPU-P4 | P3 attack 接收门禁通过 | 需要真实 CEG detector backend 产出正式 score / threshold / ablation observation | `ceg_detection/detection_events.json`, `detection_thresholds.json`, detector manifest, ablation observations |
| GPU-P5 | P4 detection 接收门禁通过 | 外部 baseline 可能依赖 GPU、外部仓库或预生成正式 observation | `external_baselines/baseline_observations.json`, baseline manifest, evidence report |
| GPU-P6 | P2 / P3 产物可用 | LPIPS、FID、CLIP score 等高级指标通常需要 GPU 或外部评估环境 | `external_metrics/metric_rows.json`, metric manifest, evidence report |

如果某个阶段由外部服务或已有正式文件完成, 也必须提供可复核 evidence path, 不能只提供口头结论或截图。

---

## 5. P0 交接清单: 当前最先需要用户填写

当前必须先填写:

```text
D:\content\drive\MyDrive\CEG\pilot_runs\real_pilot_input_workspace_20260617_034500\pilot_input_value_pack_fill_sheet.csv
```

只修改 `value_json` 列。不得修改 `task_id`、`relative_path`、`json_path`、`replacement_key` 或说明列。

当前必须填写的字段为:

| 序号 | replacement_key | JSON 类型 | 说明 |
|---:|---|---|---|
| 1 | `prompt_text` | string | 真实图像生成 prompt |
| 2 | `prompt_family` | string | prompt 分组类别 |
| 3 | `license_note` | string | prompt 来源或授权说明 |
| 4 | `split` | string | `calibration` 或 `test` |
| 5 | `sample_role` | string | `clean_negative` 或 `positive_source` 等样本角色 |
| 6 | `seed` | integer | 图像生成随机种子 |
| 7 | `seed_role` | string | `primary` 或 `replicate` |
| 8 | `backend_type` | string | `diffusers`、`external_command` 或内部 backend 标识 |
| 9 | `model_id` | string | SD 模型 ID、本地路径或外部服务标识 |
| 10 | `scheduler` | string | 采样调度器名称 |
| 11 | `num_inference_steps` | positive integer | 推理步数 |
| 12 | `guidance_scale` | positive number | classifier-free guidance scale |
| 13 | `image_size` | array | 例如 `[512, 512]` |
| 14 | `requires_huggingface_token` | boolean | `true` 或 `false`, 不能写成字符串 |
| 15 | `watermark_method` | string | CEG 或外部水印方法名称 |
| 16 | `payload_bits` | string / array / object | payload bit 串或 payload 规则 |
| 17 | `watermark_strength` | number / object | 水印嵌入强度或方法参数 |
| 18 | `backend_command` | string | 外部命令或内部 backend 标识 |
| 19 | `evidence_path` | string | backend 日志或运行 manifest 路径 |

填写完成后, 先运行只读预检:

```text
python scripts/validate_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

预检通过后, 再运行导入和 P0 聚合门禁:

```text
python scripts/import_pilot_input_value_pack_fill_sheet.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --dry-run --require-pass
python scripts/build_pilot_p0_input_freeze_report.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --require-pass
```

---

## 6. P1 到 GPU-P2 交接命令

P0 通过后, 本地生成图像生成启动计划:

```text
python scripts/scaffold_pilot_image_generation_launch_variables.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json
python scripts/build_pilot_image_generation_launch_plan.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500 --launch-variables D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_variables.draft.json --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_launch_plan_report.json --require-pass
```

当 `pilot_image_generation_launch_plan_report.json` 中满足以下条件时, 本地应暂停:

```text
overall_decision = pass
command_count > 0
```

暂停后, 用户应在真实 GPU / Colab / 外部 backend 环境中执行 launch plan 指向的图像生成与水印命令。

---

## 7. GPU 环境交回产物目录

GPU 或外部 backend 执行后, 应把产物放回同一个 MyDrive 工作区, 保持以下目录结构。

### 7.1 图像生成产物

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/clean/*
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/watermarked/*
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_pairs.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_manifests/image_generation_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images/image_manifests/image_pair_manifest.json
```

本地接收命令:

```text
python scripts/validate_pilot_image_generation_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_image_generation_output_acceptance_report.json --require-pass
```

### 7.2 attack 产物

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/attacked_images/*
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_pairs_attacked.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_manifests/attacked_image_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks/image_manifests/attack_shard_manifest.json
```

本地接收命令:

```text
python scripts/validate_pilot_attack_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/image_attacks --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_attack_output_acceptance_report.json --require-pass
```

### 7.3 CEG detection 产物

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/detection_events.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/detection_thresholds.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/ceg_detection_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection/ablation_observations.json
```

本地接收命令:

```text
python scripts/validate_pilot_detection_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/ceg_detection --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_detection_output_acceptance_report.json --require-pass
```

### 7.4 external baseline 产物

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/baseline_observations.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/baseline_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines/external_result_evidence_report.json
```

本地接收命令:

```text
python scripts/validate_pilot_baseline_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_baselines --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_baseline_output_acceptance_report.json --require-pass
```

正式论文 baseline claim 应追加:

```text
--require-formal-evidence
```

### 7.5 quality metric 产物

```text
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/metric_rows.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/metric_execution_manifest.json
D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics/quality_metric_summary_table.csv
```

本地接收命令:

```text
python scripts/validate_pilot_metric_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/external_metrics --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_metric_output_acceptance_report.json --require-pass
```

正式论文高级 metric claim 应追加:

```text
--require-formal-evidence
```

---

## 8. GPU 产物接收后的本地继续流程

当 GPU / 外部 backend 产物按目录交回并通过接收门禁后, 本地继续执行:

```text
python scripts/validate_pilot_fixed_fpr_outputs.py --output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_outputs/artifacts --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_fixed_fpr_output_acceptance_report.json --require-pass
python scripts/validate_pilot_paper_results_package.py --package-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/paper_results_package --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_paper_results_package_acceptance_report.json --require-pass
python scripts/validate_pilot_mydrive_archive.py --drive-root D:/content/drive/MyDrive/CEG --out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/pilot_mydrive_archive_acceptance_report.json --require-pass
python scripts/build_pilot_stage_progress_summary.py --workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500
```

若上述门禁失败, 应修复对应上游产物或 manifest, 不能手工改最终论文表格绕过 records 和 manifests。

---

## 9. 暂停和恢复规则

### 9.1 必须暂停的情况

本地推进遇到以下任一条件时必须暂停并交给用户执行真实环境测试:

1. 需要运行 SD / SDXL 或等价图像生成 backend。
2. 需要运行真实 watermark backend 产生 watermarked image。
3. 需要对真实图像运行 attack backend, 且本地 CPU 环境无法接受运行成本。
4. 需要运行 CEG detector backend 产生正式 score。
5. 需要运行外部 baseline backend 产生正式 observation。
6. 需要运行 LPIPS、FID、CLIP score 或其他 GPU 友好的高级指标。
7. 需要下载 gated model 或私有权重, 需要用户提供 Hugging Face token 或其他密钥。

### 9.2 可以恢复本地推进的条件

用户完成真实环境测试后, 只要对应目录和 manifest 已经放回 MyDrive 工作区, 本地即可恢复。恢复后的第一步必须是运行对应 acceptance 命令, 而不是直接构建论文结果包。

### 9.3 不能做的事情

1. 不能用本地 mock 图像替代正式 clean / watermarked / attacked 图像。
2. 不能用 dry-run detection score 计算正式 `TPR@FPR`。
3. 不能用无 evidence 的 baseline 数值支撑论文 claim。
4. 不能跳过 calibration / test split 分离。
5. 不能跳过 MyDrive 分类归档。

---

## 10. 当前下一步

当前下一步仍是 P0 输入填写, 尚未到 GPU 暂停点。具体执行顺序为:

```text
1. 用户填写 pilot_input_value_pack_fill_sheet.csv 的 19 个 value_json。
2. 本地运行 validate_pilot_input_value_pack_fill_sheet.py --require-pass。
3. 本地运行 import_pilot_input_value_pack_fill_sheet.py --require-pass。
4. 本地运行 build_pilot_p0_input_freeze_report.py --dry-run --require-pass。
5. 本地运行 build_pilot_p0_input_freeze_report.py --require-pass。
6. 本地生成 image generation launch plan。
7. 若 launch plan pass 且 command_count > 0, 暂停并交给用户在真实 GPU 环境运行。
```

只有第 7 步到达后, 才进入本文档定义的 GPU-P2 暂停点。
