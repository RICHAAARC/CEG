# CEG 论文发表推进阶段计划执行稿

## 0. 文档定位

本文档落盘于 `D:\Code\CEG\docs\builds`，用于把当前阶段计划整理为后续工程执行、实验排期和论文结果包验收的统一依据。整理日期为 2026-06-17。

本文档只定义推进顺序、门禁和产物契约，不声明当前项目已经完成正式论文实验。当前 `CEG` 已具备较多 dry-run、manifest、结果包和审计能力，但仍需要真实 SD / watermark / attack / detection / external baseline / advanced quality metric 结果，才能形成论文可用结果包。

---

## 1. 总目标

最终目标是形成一个可供论文撰写和发表使用的 `paper_results_package`。该结果包必须能够重建论文中的数据表格、统计图、示例水印图像、攻击后图像、质量指标、TPR@FPR 表、外部 baseline 对比表和审计报告。

推荐完整流程如下:

```text
prompt plan
-> clean image generation
-> watermarked image generation
-> attack execution
-> CEG detection
-> internal ablation detection
-> external baseline detection
-> quality metric evaluation
-> fixed-FPR threshold calibration
-> TPR@FPR / robustness / quality / ablation statistics
-> paper tables / figures / image examples / reports
-> paper_results_package
-> MyDrive archived result package
```

---

## 2. 当前阶段判断

### 2.1 当前可认为已经具备的能力

```text
1. 论文结果包目录和 manifest 契约已经建立。
2. dry-run 级 prompt 到图像 manifest 链路已经建立。
3. dry-run 级 attack manifest 链路已经建立。
4. CEG detection event producer 和外部 detector command plan 契约已经建立。
5. external baseline observation 适配和 pilot producer 已建立。
6. quality metric runner 的轻量 CPU 链路和离线导入入口已建立。
7. fixed-FPR / TPR@FPR 统计模块已具备雏形。
8. pilot_input_manifest、materializer、preflight 和 raw builder 已建立。
9. MyDrive 分类归档能力已建立。
10. external_result_evidence_report 可作为外部 baseline 和高级 metric 正式声明的前置证据门禁。
```

### 2.2 当前不能宣称已经具备的能力

```text
1. 不能宣称已经完成真实 SD 图像生成正式实验。
2. 不能宣称已经完成真实 watermark backend 正式实验。
3. 不能宣称已经完成正式 attack 全量实验。
4. 不能宣称已经完成真实 CEG detector 全量分数。
5. 不能宣称已经完成真实外部 baseline 全量运行。
6. 不能宣称已经完成正式 LPIPS / FID / CLIP score 高级指标。
7. 不能宣称当前 dry-run 数值可支撑论文结论。
```

### 2.3 当前阶段名称

当前阶段应命名为:

```text
pilot_input_and_external_evidence_gate_completion
```

该阶段的核心目标是: 在启动真实 pilot 前，把所有输入产物、外部 baseline 证据、高级质量指标证据和结果包归档链路固化为可审计门禁。

---

## 3. 必须坚持的论文产物原则

```text
1. 所有正式论文表格必须由 governed records 和 manifests 重建。
2. 所有示例图必须有 image_example_manifest.json 追溯来源。
3. 所有 attack 结果必须有 attack_family、attack_condition 和 attack_params。
4. TPR@FPR 的阈值必须只由 calibration clean negative 选择。
5. test clean negative 只能用于复核 FPR，不能参与阈值选择。
6. external baseline 可以来自外部仓库、Colab 或离线文件，但进入 CEG 时必须适配为统一 records 或 baseline observations。
7. external baseline 和高级 metric 若要支撑正式论文声明，必须通过 external_result_evidence_report 证据门禁。
8. Notebook 只能调度流程，不能手写正式 records、tables、figures 或 reports。
9. 本地 dry-run 只能证明工程链路，不证明论文性能。
10. 结果包必须落盘归档到 `D:\content\drive\MyDrive\CEG` 或 `/content/drive/MyDrive/CEG` 的分类目录。
```

---

## 4. 分阶段推进计划

## 阶段 A: 结果包契约冻结

### 目标

冻结论文发表结果包应包含的目录、核心文件、可选文件、审计报告和分类归档规则。

### 必需产物

```text
paper_results_package/
  artifacts/
  latex_tables/
  rendered_figures/
  pdf_figures/
  image_manifests/
  image_examples/
  detection_results/
  baseline_results/
  metric_results/
  paper_results_report.md
  paper_readiness_report.json
  paper_results_report_manifest.json
  paper_results_package_manifest.json
```

### 当前状态

```text
基本完成，后续只随新增正式产物维护。
```

### 完成门禁

```text
1. paper_results_package_manifest.json 能索引所有应归档文件。
2. paper_readiness_report.json 能报告缺失 required artifacts。
3. MyDrive 归档能按 package_snapshots、package_archives、package_manifests 分类保存。
```

---

## 阶段 B: pilot 输入 manifest 门禁

### 目标

用 `pilot_input_manifest.json` 固化一次 pilot 或正式实验所需的全部输入，避免后续手工传递零散路径。

### 推荐输入

```text
events
thresholds
baseline_observations
baseline_execution_manifest
metric_rows
metric_execution_manifest
detection_execution_manifest
image_pairs
attacked_image_manifest
attack_shard_manifest
experiment_matrix
readiness_requirements
detection_output_root
```

### 当前状态

```text
已建立 template、materializer、validator 和 raw builder 接口。
```

### 下一步

```text
1. 用真实或半真实 pilot 产物生成 pilot_input_manifest.json。
2. 运行 scripts/validate_pilot_input_manifest.py。
3. 若输入分散，先运行 scripts/materialize_pilot_input_manifest.py 生成 canonical 输入目录。
4. 构建结果包时优先使用 --pilot-input-manifest，而不是手工传入大量路径。
```

### 完成门禁

```text
1. manifest 声明的所有路径均能解析。
2. events、thresholds、baseline observations、metric rows 能通过轻量 schema 校验。
3. preflight 报告进入 package build manifest。
```

---

## 阶段 C: 外部结果证据门禁

### 目标

对 external baseline 和高级 quality metric 的正式声明增加证据前置检查，避免将 mock、dry-run 或无来源的离线文件包装成正式论文结果。

### 核心产物

```text
external_result_evidence_report.json
baseline_execution_manifest.json
metric_execution_manifest.json
```

### 当前状态

```text
已建立 validate_external_result_evidence.py 和 raw builder 的 --check-external-result-evidence / --require-formal-external-result-claim 开关。
```

### 下一步

```text
1. 确保 baseline_execution_manifest.json 声明 backend、command、input、output 和 evidence_paths。
2. 确保 metric_execution_manifest.json 声明 backend、metric families、input、output 和 evidence_paths。
3. 正式论文声明前启用 --require-formal-external-result-claim。
4. 将 external_result_evidence_report.json 随 paper_results_package 一起归档，便于论文结果包复核。
```

### 完成门禁

```text
1. formal_result_claim 为 true 时必须存在可解析 evidence_paths。
2. external_result_evidence_report.json 必须为 pass。
3. 不允许无证据 external baseline 或高级 metric 支撑 supported claims。
```

---

## 阶段 D: 真实图像生成 pilot

### 目标

用真实 SD 或外部生成 backend 产生 clean / watermarked 图像，并形成可追溯 image manifests。

### 输入

```text
prompt_plan.json
model_config.json
seed_plan.json
split_plan.json
watermark_config.json
```

### 输出

```text
image_generation_manifest.json
image_pair_manifest.json
clean images
watermarked images
```

### 当前状态

```text
dry-run mock backend 已打通，external backend command plan 已具备，但真实 SD / watermark pilot 尚未完成。
```

### 完成门禁

```text
1. clean / watermarked 图像文件真实存在。
2. 每张图像可追溯 prompt、seed、model_id、scheduler、watermark method 和 split。
3. image_pair_manifest.json 能被 attack、detection 和 quality metric 阶段消费。
```

---

## 阶段 E: attack pilot

### 目标

对 watermarked 图像执行最小 attack 集合，产生 attacked 图像和 attack provenance。

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
attacked_image_manifest.json
attack_shard_manifest.json
attacked images
```

### 当前状态

```text
dry-run 契约链路已打通，正式真实图像 attack pilot 尚未完成。
```

### 完成门禁

```text
1. attacked_image_path 均存在。
2. attack_family、attack_condition 和 attack_params 完整记录。
3. detection 阶段能同时消费 clean、watermarked 和 attacked 图像。
```

---

## 阶段 F: CEG detection 与内部消融 pilot

### 目标

运行真实或半真实 CEG detector backend，产生统一 detection events 和 thresholds。

### 必须覆盖

```text
CEG Full
CEG Content-only
CEG Recover-then-Content
CEG No-rescue
CEG No-attestation
```

### 输出

```text
detection_events.json
detection_thresholds.json
ceg_detection_execution_manifest.json
```

### 当前状态

```text
dry-run producer 与 external detector command plan 已具备，真实 detector backend 小样本尚未完成。
```

### 完成门禁

```text
1. 每条 detection event 包含 method_name、split、sample_role、score、higher_is_positive。
2. attacked 样本包含 attack_family 和 attack_condition。
3. thresholds 与 calibration / test split 关系清晰。
```

---

## 阶段 G: external baseline pilot

### 目标

至少接入一个真实 external baseline，并最终扩展到论文计划中的全部 baseline。

### 目标 baseline

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 输出

```text
baseline_observations.json
baseline_execution_manifest.json
baseline_comparison_table.csv
```

### 当前状态

```text
dry-run / pilot producer 和离线导入入口已建立，真实 baseline backend 或正式离线 observation 尚未完成。
```

### 完成门禁

```text
1. 至少一个 baseline 有真实运行证据。
2. baseline_observations.json 可进入统一统计链路。
3. baseline_execution_manifest.json 通过 external evidence preflight。
4. baseline_comparison_table.csv 可由 records 和 manifests 重建。
```

---

## 阶段 H: quality metric pilot

### 目标

为论文提供图像质量和水印质量指标。

### 指标范围

```text
PSNR
SSIM
LPIPS
FID
CLIP score
bit accuracy
payload recovery rate
```

### 当前状态

```text
CPU 轻量 MSE、MAE、PSNR、全局 SSIM runner 已具备。LPIPS、FID、CLIP score 需真实 backend 或正式离线导入。
```

### 完成门禁

```text
1. metric_rows.json 可被导入并聚合。
2. metric_execution_manifest.json 记录执行环境、输入、输出和证据路径。
3. 高级指标正式声明通过 external evidence preflight。
```

---

## 阶段 I: fixed-FPR / TPR@FPR 统计

### 目标

生成论文主表所需的 fixed-FPR 阈值和 TPR@FPR 统计结果。

### 正式口径

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive -> clean/watermarked TPR@FPR
attacked positive -> attack TPR@FPR
```

### 输出

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
对应 LaTeX 表
```

### 完成门禁

```text
1. TPR@1%FPR 可复现。
2. 若样本量足够，TPR@0.1%FPR 可复现。
3. 阈值选择和测试评估严格分离。
4. attack TPR 按 attack_family 和 attack_condition 分组。
```

---

## 阶段 J: 论文示例图与图表重建

### 目标

形成论文撰写可直接引用的图像示例、comparison grid、统计图和 LaTeX 表。

### 输出

```text
image_examples/
rendered_figures/
pdf_figures/
latex_tables/
paper_results_report.md
paper_claim_audit.json
```

### 完成门禁

```text
1. 示例图文件真实存在。
2. image_example_manifest.json 追溯 prompt、seed、method、attack 和 detection record。
3. LaTeX 表和 rendered figures 可由 records 和 manifests 重建。
4. paper_claim_audit.json 不使用 placeholder 字段支撑正式 claim。
```

---

## 阶段 K: Colab pilot 与 MyDrive 归档

### 目标

在 Colab 或 GPU 环境执行小规模真实 pilot，并把结果包归档到 MyDrive。

### 推荐 pilot 规模

```text
prompt: 8 到 16
seed: 1 到 2
method: CEG + 1 到 2 个 external baseline
attack: jpeg + resize + brightness_contrast
split: calibration + test
```

### 输出

```text
paper_results_package/
paper_results_package.zip
colab_run_bundle.zip
MyDrive package_snapshots/
MyDrive package_archives/
MyDrive package_manifests/
```

### 完成门禁

```text
1. pilot 结果包能从 pilot_input_manifest.json 一键构建。
2. paper_readiness_report.json 为 pass 或明确列出非正式缺口。
3. colab_acceptance_report.json 为 pass。
4. 归档目录位于 `D:\content\drive\MyDrive\CEG` 或 `/content/drive/MyDrive/CEG`。
```

---

## 阶段 L: 正式论文实验

### 目标

运行完整规模实验，生成论文撰写和投稿可用结果包。

### 必须包含

```text
完整 prompt set
完整 clean / watermarked / attacked images
完整 CEG + internal ablation
完整 external baselines
完整 quality metrics
完整 fixed-FPR / TPR@FPR
完整 paper figures
完整 LaTeX tables
完整 image examples 和 comparison grids
完整 paper_results_report.md
完整 paper_results_package.zip
完整 colab_run_bundle.zip
```

### 完成门禁

```text
paper_result_evidence_report.json = pass
external_result_evidence_report.json = pass
paper_readiness_report.json = pass
paper_claim_audit.json = pass
colab_acceptance_report.json = pass
colab_formal_result_gap_report.json = ready_for_formal_claims
```

---

## 5. 立即执行顺序

当前最推荐的下一步执行顺序如下:

```text
1. 选定一组真实或半真实 pilot 输入文件。
2. 生成 pilot_input_manifest.json。
3. 运行 pilot input preflight。
4. 如果包含外部 baseline 或高级 metric 正式声明，运行 external result evidence preflight。
5. 将 external_result_evidence_report.json 纳入 paper_results_package 归档。
6. 用 raw builder 或 provided-results builder 构建 paper_results_package。
7. 归档到 MyDrive 分类目录。
8. 检查 readiness、claim audit、package manifest 和 Colab acceptance。
9. 再启动真实 SD / watermark / attack / CEG detector / external baseline pilot。
10. pilot 通过后冻结正式实验配置。
```

---

## 6. 不应优先做的事项

```text
1. 不应先手工拼接论文表格。
2. 不应先手工挑选论文示例图并绕过 image_example_manifest.json。
3. 不应在没有 calibration / test split 的情况下统计 TPR@FPR。
4. 不应把 dry-run 图像或 mock 分数写成论文实验结论。
5. 不应在没有 external_result_evidence_report 的情况下声明外部 baseline 或高级 metric 的正式结果。
```

---

## 7. 与 D:\Code\CEG-WM 的方法机制对齐要求

后续 `CEG` 应继续与 `CEG-WM` 保持以下核心机制一致:

```text
1. prompt / split / shard / experiment plan 先行。
2. clean negative calibration 与 test evaluation 分离。
3. attack 是鲁棒性统计的独立阶段，不并入图像生成阶段。
4. detection scores 进入统一 records。
5. external baseline 进入统一 observation 或 event schema。
6. fixed-FPR threshold table、TPR@FPR table 和 attack TPR table 由 records 重建。
7. paper package 只归档可追溯 artifacts，不归档无 provenance 的手工结果。
```

---

## 8. 本文档与已有文档关系

```text
docs/builds/ceg_method_mechanism.md:
  记录 CEG 项目当前真实方法机制。

docs/builds/ceg_wm_method_alignment_audit.md:
  记录 CEG 与 CEG-WM 的机制一致性审计。

docs/builds/paper_publication_phase_plan.md:
  记录较完整的论文发表阶段计划。

docs/builds/paper_publication_result_package_plan.md:
  记录结果包契约和论文产物边界。

docs/builds/paper_publication_execution_stage_plan.md:
  本文档，作为当前最直接的执行顺序和阶段门禁索引。
```
