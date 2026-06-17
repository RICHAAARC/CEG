# 顶会论文结果包需求说明

## 1. 文档目的

本文档用于明确 `D:\Code\CEG` 项目面向顶会论文发表时, 结果包应包含的输入、图像、记录、统计、图表、报告和可复核材料。

该文档属于论文产物治理说明, 不等同于已经完成正式实验。其作用是定义后续实现、Colab 运行、结果打包和论文撰写所必须满足的目标契约。

## 2. 顶会论文结果包的核心原则

一个可用于顶会论文撰写和审稿复核的结果包, 不能只包含 notebook 输出日志或若干示例图像。它必须满足以下原则:

1. 论文中的每一个核心数值结论都必须能追溯到 records。
2. 论文中的每一张表格和图都必须能由 records 与 manifests 重建。
3. clean、watermarked、attacked 图像必须可追溯到 prompt、seed、模型、水印方法、攻击条件和检测记录。
4. fixed-FPR 指标必须使用 calibration split 定阈值, 再在 test split 上报告。
5. baseline 对比必须保留 baseline 的输入、输出、检测记录、统计记录和 manifest。
6. 论文示例图像必须来自正式图像产物, 不能手工挑图后脱离 provenance。
7. 结果包必须能离线复核, 包含配置、摘要、重建命令、验收报告和审计报告。

## 3. 结果包应包含的目录结构

建议最终结果包采用以下结构:

```text
result_packages/
  paper_main_run_<run_id>/
    configs/
    prompts/
    images/
      clean/
      watermarked/
      attacked/
      examples/
    records/
    manifests/
    statistics/
    quality/
    baselines/
    tables/
    figures/
    reports/
    audits/
    result_package_manifest.json
    rebuild_commands.md
```

各目录职责如下:

| 目录 | 职责 |
|---|---|
| `configs/` | 保存模型、水印、攻击、检测、baseline、实验矩阵配置 |
| `prompts/` | 保存 prompt plan 与 prompt 来源 manifest |
| `images/clean/` | 保存由 SD 或指定图像生成模型产生的 clean 图像 |
| `images/watermarked/` | 保存正式水印方法生成的 watermarked 图像 |
| `images/attacked/` | 保存攻击后的图像 |
| `images/examples/` | 保存论文示例图, 来源必须可追溯 |
| `records/` | 保存检测、calibration、attack、baseline 等事件级记录 |
| `manifests/` | 保存图像、攻击、检测、metric、baseline、结果包 manifest |
| `statistics/` | 保存 fixed-FPR、TPR、置信区间、攻击鲁棒性等统计表 |
| `quality/` | 保存 PSNR、SSIM、LPIPS、FID、CLIP score 等质量指标 |
| `baselines/` | 保存外部 baseline 相关结果与 provenance |
| `tables/` | 保存论文表格 CSV / LaTeX / Markdown 版本 |
| `figures/` | 保存论文图的数据源与渲染结果 |
| `reports/` | 保存论文结果摘要、claim audit、readiness report |
| `audits/` | 保存验收、复核、完整性审计报告 |

## 4. 必需输入材料

论文结果包至少应包含以下输入材料:

```text
prompts/
  prompt_plan.json
  prompt_source_manifest.json

configs/
  model_config.json
  watermark_config.json
  attack_config.json
  detection_config.json
  baseline_config.json
  experiment_matrix.json
```

关键字段包括:

| 字段 | 含义 |
|---|---|
| `prompt_id` | prompt 的稳定 ID |
| `prompt_text` | 图像生成 prompt |
| `image_id` | 图像稳定 ID |
| `event_id` | 实验事件稳定 ID |
| `model_id` | SD 模型 ID、本地路径或等价模型来源 |
| `seed` | 图像生成随机种子 |
| `method_name` | 方法名称, 如 CEG 或 baseline 名称 |
| `split` | calibration / test / validation 等拆分 |
| `sample_role` | clean negative、positive、attacked positive 等样本角色 |
| `attack_family` | 攻击类别 |
| `attack_condition` | 攻击强度或条件 |

## 5. 必需图像产物

图像水印论文必须产出真实图像产物。最小要求如下:

```text
images/
  clean/
  watermarked/
  attacked/
  examples/
```

其中:

1. `clean/` 保存未嵌入水印的图像。
2. `watermarked/` 保存正式水印方法输出的图像。
3. `attacked/` 保存对 watermarked 图像施加攻击后的图像。
4. `examples/` 保存论文中展示的示例图像, 包括 clean、watermarked、差分图、attacked 图。

重要要求:

- watermarked 图像不能是 clean 图像的复制。
- attacked 图像必须记录攻击来源与攻击参数。
- 示例图像必须来自正式 image pair records, 不能脱离 provenance 手工拼接。

## 6. 必需 manifests

结果包至少应包含:

```text
manifests/
  image_generation_manifest.json
  image_pair_manifest.json
  attack_manifest.json
  detection_manifest.json
  metric_manifest.json
  baseline_manifest.json
  result_package_manifest.json
```

manifest 的作用是说明:

1. 哪些 prompt 与 seed 生成了哪些 clean 图像。
2. 哪些 clean 图像生成了哪些 watermarked 图像。
3. 哪些 watermarked 图像经过了哪些 attack。
4. 哪些 attacked 图像进入了 detection。
5. 哪些 detection records 进入了 fixed-FPR 统计。
6. 哪些统计结果重建了论文表格与图。

## 7. 必需 records

正式统计应以 records 为事实来源。至少应包含:

```text
records/
  detection_records.jsonl
  calibration_records.jsonl
  attack_detection_records.jsonl
  baseline_detection_records.jsonl
```

每条 detection record 至少应包含:

| 字段 | 含义 |
|---|---|
| `image_id` | 图像 ID |
| `event_id` | 检测事件 ID |
| `method_name` | 方法名称 |
| `is_watermarked_ground_truth` | 是否真实带水印 |
| `attack_family` | 攻击类别 |
| `attack_condition` | 攻击条件 |
| `score` | 检测分数 |
| `decision` | 检测判定 |
| `threshold` | 当前 operating point 阈值 |
| `split` | calibration 或 test |
| `sample_role` | 样本角色 |

## 8. fixed-FPR 统计需求

若论文报告 `TPR@FPR`, 必须严格区分 calibration 与 test。

最小产物包括:

```text
statistics/
  fixed_fpr_threshold_table.csv
  tpr_at_fixed_fpr_table.csv
  attack_tpr_at_fixed_fpr_table.csv
  baseline_comparison_table.csv
  confidence_intervals.csv
```

统计规则:

1. 使用 `calibration clean negative` 定阈值。
2. 使用 `test clean negative` 估计 empirical FPR。
3. 使用 `test positive` 估计 clean condition 下的 TPR。
4. 使用 `attacked positive` 估计攻击后的 TPR。
5. baseline 必须使用相同 target FPR 口径或明确记录其等价 operating point。

## 9. 图像质量指标需求

图像水印论文必须报告视觉质量。最小指标建议为:

```text
quality/
  psnr_table.csv
  ssim_table.csv
  lpips_table.csv
  quality_summary.csv
```

顶会论文建议进一步包含:

```text
quality/
  fid_table.csv
  clip_score_table.csv
  human_preference_summary.csv
```

质量指标至少应支持以下结论:

1. watermarked 图像与 clean 图像视觉差异较小。
2. 方法不是通过严重破坏图像换取检测率。
3. 与 baseline 相比, CEG 在质量与鲁棒性之间具有更优权衡。

## 10. baseline 对比需求

结果包必须包含外部 baseline, 不能只报告 CEG 自身结果。

建议 baseline 包括:

```text
baselines/
  tree_ring/
  stable_signature/
  gaussian_shading/
  shallow_diffuse/
```

每个 baseline 至少应包含:

1. baseline 配置。
2. baseline 图像输出或检测记录。
3. baseline metric rows。
4. baseline manifest。
5. baseline 与 CEG 的同口径 fixed-FPR 统计结果。

## 11. 论文应产出的核心表格

### 11.1 主结果表

主结果表用于回答方法是否整体优于 baseline。

建议字段:

```text
Method | TPR@1%FPR | TPR@0.1%FPR | AUROC | PSNR | SSIM | LPIPS
```

支撑文件:

```text
statistics/tpr_at_fixed_fpr_table.csv
statistics/baseline_comparison_table.csv
quality/quality_summary.csv
```

### 11.2 攻击鲁棒性表

建议字段:

```text
Attack | Strength | Method | TPR@1%FPR | Empirical FPR | Delta vs Clean
```

攻击建议包括:

- JPEG compression
- Gaussian noise
- Gaussian blur
- Crop
- Resize
- Rotation
- Color jitter
- Diffusion regeneration
- Screenshot / compression pipeline

支撑文件:

```text
statistics/attack_tpr_at_fixed_fpr_table.csv
manifests/attack_manifest.json
```

### 11.3 消融实验表

建议字段:

```text
Variant | TPR@1%FPR | PSNR | LPIPS | Failure Mode
```

消融项建议包括:

- Full CEG
- Content-only
- No geometry rescue
- No attestation
- No semantic mask
- No HF component
- No LF component
- No InSPyReNet mask

### 11.4 固定 FPR 阈值表

建议字段:

```text
Target FPR | Threshold | Empirical FPR | Calibration N | Test N
```

该表用于证明 fixed-FPR 不是事后调参。

### 11.5 运行成本表

建议字段:

```text
Method | Generation Time | Detection Time | GPU Memory | Model
```

该表用于说明方法是否具备实际可用性。

## 12. 论文应产出的核心图

### 12.1 方法流程图

内容应包括:

```text
Prompt
→ SD generation
→ semantic mask / InSPyReNet
→ watermark embedding
→ attack
→ detection
→ fixed-FPR decision
```

### 12.2 示例图像对比图

建议展示:

```text
clean image
watermarked image
absolute difference / amplified residual
attacked image
```

### 12.3 ROC 曲线

建议展示:

```text
CEG vs baselines ROC
```

### 12.4 TPR 随攻击强度变化曲线

示例:

```text
JPEG quality 从 95 到 30
Gaussian noise sigma 从 0 到 0.1
Crop ratio 从 1.0 到 0.5
```

### 12.5 质量-鲁棒性权衡图

建议坐标:

```text
x-axis: LPIPS 或 PSNR
y-axis: TPR@1%FPR
```

### 12.6 消融柱状图

展示 Full CEG 与各变体在 fixed-FPR 指标下的差异。

## 13. 论文应支撑的核心结论

### 13.1 主性能结论

结论形式:

```text
CEG 在固定 FPR 下相比 baseline 获得更高 TPR。
```

支撑产物:

```text
statistics/tpr_at_fixed_fpr_table.csv
statistics/baseline_comparison_table.csv
```

### 13.2 鲁棒性结论

结论形式:

```text
CEG 在 JPEG、resize、crop 等攻击下保持更稳定检测率。
```

支撑产物:

```text
statistics/attack_tpr_at_fixed_fpr_table.csv
manifests/attack_manifest.json
```

### 13.3 视觉质量结论

结论形式:

```text
CEG 在保持较高检测率的同时维持较低感知失真。
```

支撑产物:

```text
quality/quality_summary.csv
images/examples/
```

### 13.4 消融结论

结论形式:

```text
semantic mask、geometry rescue、attestation 等模块分别提升鲁棒性、低误报控制和攻击后恢复能力。
```

支撑产物:

```text
statistics/ablation_table.csv
records/ablation_detection_records.jsonl
```

### 13.5 可复现性结论

结论形式:

```text
所有论文表格和图均可由 records 与 manifests 重建。
```

支撑产物:

```text
result_package_manifest.json
rebuild_commands.md
audits/
```

## 14. 当前项目相对顶会结果包的关键缺口

当前项目仍需要补齐以下能力, 才能支撑正式论文主结果:

1. CEG 内部正式 watermark backend。
2. InSPyReNet / semantic mask 接入。
3. 与方法设计一致的 LF / HF / geometry / attestation 水印机制。
4. 真实 detection backend。
5. attack 后检测 records。
6. fixed-FPR calibration / test 统计闭环。
7. external baseline 真实结果。
8. 图像质量指标。
9. 论文表格和图的重建脚本。
10. 结果包级 provenance 与 claim audit。

当前仅具备流程联调级图像生成和结果包骨架时, 不应把输出声明为正式论文主方法结果。

## 15. 最小合格完成判据

一个最小合格论文结果包应满足:

1. `image_generation_output_acceptance_report.overall_decision = pass`。
2. attack 输出验收通过。
3. detection 输出验收通过。
4. fixed-FPR 输出验收通过。
5. baseline 输出验收通过。
6. quality metric 输出验收通过。
7. paper result package 验收通过。
8. 所有表格和图可由 records 与 manifests 重建。
9. supported claims 均绑定到 governed artifacts。
10. 结果包 zip 可从 Google Drive 下载并离线复核。
