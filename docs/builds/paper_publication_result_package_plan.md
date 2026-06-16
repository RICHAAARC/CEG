# CEG 向论文发表结果包推进计划

## 0. 文档定位

本文档记录 `D:\Code\CEG` 后续向论文发表结果包推进的阶段计划。该计划以“形成可供论文撰写和发表使用的结果包”为最终目标, 而不是以 clean project 范围收缩为目标。

最终结果包应能够支撑论文中的:

```text
正式数据表格
LaTeX 表格
论文图表
示例 clean / watermarked / attacked 图像
图像水印标准评价指标
TPR@FPR / fixed-FPR 统计
CEG 内部消融
外部 baseline 对比
可复核 provenance 与 manifest
```

本文档属于阶段计划和交付契约说明, 不声明当前已经产出正式论文结果。当前本地 dry-run 只能证明工程链路可运行, 不能替代真实 SD / watermark / attack / detection 实验。

---

## 1. 总体目标

### 1.1 最终目标

构建一个可复现的论文结果包生成流程:

```text
prompt plan
-> SD 或外部生成 backend 生成 clean / watermarked 图像
-> attack workflow 生成 attacked 图像
-> CEG detection 与内部 ablation detection
-> 外部 baseline detection
-> 图像质量与水印标准指标计算
-> fixed-FPR threshold calibration
-> TPR@FPR / AUROC / quality / robustness / ablation 统计
-> 论文表格、图表、示例图和报告
-> paper_results_package 与 colab_run_bundle
```

### 1.2 当前已经具备的基础

当前 `CEG` 已经具备以下基础能力:

```text
CEG formal decision runtime
CEG 内部消融记录
外部 baseline observation 适配
标准指标聚合
论文表格 / 图表 / LaTeX 表重建
paper_results_package 导出
Colab dry-run 冷启动 helper
Colab bundle / archive / acceptance 校验
result index 对 required artifacts 和 LaTeX tables 的覆盖门禁
```

### 1.3 当前缺口

当前仍缺少正式论文发表所需的上游真实实验层:

```text
prompt 到图像生成计划
真实 SD / watermark 图像生成或外部生成 backend 接入
attack 图像生成和 attack manifest
检测分数生产链路
CEG-WM 风格 fixed-FPR threshold calibration
TPR@FPR 正式统计表
示例图选择与 image_examples 结果包目录
外部 baseline 从执行到结果表的正式 pilot 验证
pilot_input_manifest.json 统一输入门禁与 preflight 报告接入一键结果包构建流程
```

---

## 2. attack 是否必须以及应放在哪个阶段

### 2.1 结论

对于图像水印论文, attack 基本属于必需评价流程。

如果论文包含以下主张, attack 就必须进入正式实验:

```text
robust watermark
鲁棒性
攻击后仍可检测
geometry rescue
恢复链贡献
与外部 baseline 的公平对比
```

如果完全不做 attack, 论文只能证明 clean detection, 难以支撑图像水印论文常见的鲁棒性声明。

### 2.2 attack 不应并入生成流程

attack 不应并入 prompt / SD 生成阶段, 因为生成阶段负责产生原始 clean / watermarked 图像, attack 阶段负责评价这些图像在扰动后的可检测性。

推荐边界如下:

```text
生成阶段: prompt -> clean image / watermarked image
attack 阶段: watermarked image -> attacked image
detection 阶段: clean / watermarked / attacked image -> detection scores
统计阶段: scores -> threshold / TPR@FPR / robustness / tables
```

### 2.3 attack 在 CEG workflow 中的位置

推荐在 `CEG` 中采用类似 `CEG-WM` 的阶段拆分:

```text
PW00: prompt / split / shard / experiment plan
PW01: source image generation and watermark image generation
PW02: clean negative merge and fixed-FPR threshold calibration
PW03: attack shard execution
PW04: attack merge, detection metrics, quality metrics and paper tables
PW05: paper results package export
```

其中 attack 对应 `PW03`, 统计和论文结果汇总对应 `PW04`。

---

## 3. 阶段计划

## 阶段 1: 冻结论文发表结果包契约

### 目标

明确最终论文结果包必须包含的目录、文件、manifest、表格、图表和示例图, 避免后续跑出无法进入论文结果包的中间产物。

### 建议目录

```text
paper_results_package/
  artifacts/
  latex_tables/
  rendered_figures/
  pdf_figures/
  image_examples/
  image_manifests/
  baseline_results/
  fixed_fpr/
  paper_results_report.md
  paper_claim_audit.json
  paper_readiness_report.json
  paper_results_package_manifest.json
```

### 新增或强化产物

```text
image_generation_manifest.json
image_pair_manifest.json
attacked_image_manifest.json
image_example_manifest.json
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
baseline_execution_manifest.json
```

### 完成标准

```text
configs/paper_output_requirements.json 明确记录新增必需产物
paper_results_package_manifest.json 能索引新增目录和文件
paper_readiness_report 能检查新增产物存在性
colab_paper_result_index 能逐项索引新增产物
```

---

## 阶段 2: prompt 到图像样本 manifest 的真实实验层

### 目标

让 `CEG` 能组织真实图像实验, 而不是只消费已经生成好的分数。

### 输入

```text
prompt_plan.json
model_config.json
seed_plan.json
split_plan.json
```

### 输出

```text
image_generation_manifest.json
image_pair_manifest.json
```

### 每条图像记录至少包含

```text
image_id
prompt_id
prompt_text
seed
model_id
scheduler
num_inference_steps
guidance_scale
split
sample_role
clean_image_path
watermarked_image_path
```

### 实现建议

先支持两类 backend:

```text
mock_backend: 本地测试用, 不调用 SD, 只生成小型占位图或使用 fixture 图像
external_backend: Colab 正式运行用, 调用外部 SD / watermark 脚本并回收 manifest
```

### 完成标准

```text
本地 mock backend 可生成小样本 manifest
Colab external backend 可接入真实生成脚本
manifest 可被后续 attack / detection / quality metric 阶段消费
```

---

## 阶段 3: attack workflow

### 目标

对 watermarked image 产生攻击后图像, 并记录攻击 provenance。

### 最小 attack 集合

```text
jpeg
crop
resize
rotate
gaussian_noise
gaussian_blur
brightness_contrast
```

### 后续可选 attack

```text
vae_reconstruction
diffusion_regeneration
combined_attack
```

### 输入

```text
image_pair_manifest.json
attack_plan.json
```

### 输出

```text
attacked_image_manifest.json
attack_shard_manifest.json
```

### 每条 attacked image 记录至少包含

```text
attacked_image_id
source_image_id
watermarked_image_path
attacked_image_path
attack_family
attack_condition
attack_params
split
sample_role
```

### 完成标准

```text
本地 mock / CPU attack 可生成小规模 attacked 图像
正式 Colab 可按 shard 运行 attack
attack manifest 可被 detection 和 paper package 消费
```

---

## 阶段 4: CEG detection 与外部 baseline 统一适配

### 目标

将 CEG、内部消融和外部 baseline 的检测输出统一进入 records。

### 必须覆盖的方法

```text
CEG
CEG Full
CEG Content-only
CEG Recover-then-Content
CEG No-rescue
CEG No-attestation
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 输入

```text
image_pair_manifest.json
attacked_image_manifest.json
thresholds.json
baseline command plans
```

### 输出

```text
event_records.json
baseline_observations.json
baseline_execution_manifest.json
```

### 统一记录字段

```text
event_id
method_name
baseline_id
split
sample_role
attack_family
attack_condition
is_watermarked
score
threshold
higher_is_positive
content_score_raw
content_score_aligned
attestation_score
geometry fields
bit recovery fields
quality fields
```

### 完成标准

```text
CEG 与所有外部 baseline 均进入统一 records
baseline_comparison_table.csv 可由 records 重建
method_group_comparison_table.csv 可区分 proposed / ablation / external baseline
method_pairwise_delta_table.csv 可比较 CEG 与 ablation / external baseline
```

---

## 阶段 5: fixed-FPR / TPR@FPR 正式统计

### 目标

对齐论文发表口径, 使用 calibration clean negative 校准 fixed-FPR 阈值, 再在 test / attacked split 上评估 TPR。

### 正式口径

```text
calibration clean negative -> threshold_at_fpr
test clean negative -> test_fpr_at_threshold
test positive / attacked positive -> tpr_at_fixed_fpr
```

### 目标 FPR

```text
1 percent FPR
0.1 percent FPR
```

### 新增模块建议

```text
main/analysis/fixed_fpr.py
```

### 新增产物

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
```

### 完成标准

```text
TPR@1%FPR 和 TPR@0.1%FPR 可由 records 重建
阈值选择只使用 calibration clean negative
test clean negative 只用于复核 FPR, 不参与选阈值
attacked positive 用于统计 attack robustness 下的 TPR@FPR
```

---

## 阶段 6: 标准图像水印指标与示例图

### 目标

结果包不仅包含统计表, 还包含论文撰写可用的示例图和标准图像质量指标。

### 标准指标

```text
PSNR
SSIM
LPIPS
FID
CLIP score
bit accuracy
payload recovery rate
```

### 示例图目录

```text
paper_results_package/image_examples/
  clean/
  watermarked/
  attacked/
  comparison_grids/
```

### 示例图 manifest

```text
image_example_manifest.json
```

### 每条例图记录至少包含

```text
example_id
image_id
prompt_id
method_name
attack_family
attack_condition
clean_image_path
watermarked_image_path
attacked_image_path
caption
selection_reason
```

### 完成标准

```text
论文可直接引用 image_examples 中的示例图
示例图来源可由 manifest 追溯到 prompt、seed、method、attack 和 detection record
质量指标进入 quality_metrics_summary.csv 和 standard_watermark_metrics.json
```

---

## 阶段 7: Colab 端到端论文实验入口

### 目标

新增或扩展 Colab Notebook, 使其从冷启动执行完整论文实验入口。

### 推荐 Notebook

```text
paper_workflow/colab_ceg_paper_pipeline.ipynb
```

### Notebook 只负责调度

Notebook 不应手写正式 records、tables、figures 或 reports。正式逻辑应放在:

```text
main/
experiments/
scripts/
paper_workflow/colab_utils/
paper_workflow/notebook_utils/
```

### Notebook 阶段

```text
1. 环境准备和 Drive 挂载
2. 模型 / 外部 backend 路径检查
3. prompt plan 和 split plan 准备
4. source / watermarked image generation
5. attack shard execution
6. CEG detection 和 external baseline detection
7. quality metric execution
8. fixed-FPR evaluation
9. paper results package export
10. bundle / archive / acceptance
```

### 完成标准

```text
Colab dry-run / mock backend 可全链路通过
Colab pilot 可用真实小样本生成图像和结果包
正式运行可输出 paper_results_package.zip 和 colab_run_bundle.zip, 且 paper_results_package 可按 package_snapshots / package_archives / package_manifests 分类归档到 MyDrive
```

---

## 阶段 8: pilot 实验

### 目标

先运行小规模真实或半真实 pilot, 验证链路和统计口径, 不直接进入全量论文实验。

### 建议规模

```text
prompt: 8 到 16
seed: 1 到 2
method: CEG + 1 到 2 个 external baseline
attack: jpeg + crop + resize
split: calibration + test
```

### 完成标准

```text
clean / watermarked / attacked 图像真实存在
image manifest 完整
CEG records 完整
至少一个外部 baseline 能进入对比表
fixed-FPR 表可生成
paper_results_package 可导出, 可通过 scripts/build_pilot_package_from_provided_results.py 从已提供产物一键构建, 并可通过 scripts/archive_paper_results_to_drive.py 归档到 MyDrive 分类目录
示例图可进入 image_examples
```

---

## 阶段 9: 正式论文实验

### 目标

运行完整实验并生成可用于论文撰写的结果包。

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
示例图和 comparison grids
paper_results_report.md
paper_results_package.zip
colab_run_bundle.zip
```

### 完成标准

```text
paper_result_evidence_report.json = pass
paper_readiness_report.json = pass
paper_claim_audit.json = pass
colab_acceptance_report.json = pass
colab_formal_result_gap_report.json = ready_for_formal_claims
```

---

## 4. 推荐立即执行的下一步

建议下一步优先完成 pilot 输入门禁, 因为它决定后续真实图像实验、真实检测结果、外部 baseline 和高级指标是否能被稳定纳入论文结果包。

```text
1. 复制 configs/pilot_input_manifest_template.json, 或使用 scripts/materialize_pilot_input_manifest.py 从已提供产物自动生成某次 pilot 的 pilot_input_manifest.json。
2. 在该 manifest 中声明 events、thresholds、baseline observations、metric rows、image pairs、attack manifests、experiment matrix 和 readiness requirements。
3. 运行 pilot input preflight, 确认所有输入文件存在、路径可解析、schema 可解析。
4. 使用已支持 --pilot-input-manifest 的 scripts/build_pilot_package_from_provided_results.py, 避免手工传入一长串路径。
5. 若输入仍分散在多个外部目录, 使用 scripts/build_pilot_package_from_raw_inputs.py 单命令完成物化、preflight、结果包构建和 MyDrive 分类归档。
6. 在 preflight 通过后, 再使用一键构建脚本导出 paper_results_package 并归档到 MyDrive 分类目录。
```

随后再进入:

```text
真实 SD / watermark backend pilot
真实 CEG detector backend pilot
至少一个真实 external baseline pilot
真实 LPIPS / FID / CLIP score 或离线正式 metric rows 接入
external_result_evidence_report.json 证明确有外部 baseline 和高级 metric 运行证据
fixed-FPR / TPR@FPR 和论文示例图复核
```

这样可以避免先跑出大量图像和分数, 但后续无法按论文发表口径统计、审计和打包。

---

## 5. 风险与约束

### 5.1 本地无 GPU

本地只应运行 mock / dry-run / CPU 轻量测试。真实 SD、LPIPS、FID、CLIP score 和部分外部 baseline 应放到 Colab GPU 或其他 GPU 环境。

### 5.2 Hugging Face 密钥

`CEG` 本身不应强依赖 Hugging Face 密钥。是否需要 HF token 取决于实际选择的 SD / CLIP / baseline backend 是否使用 gated model。

### 5.3 外部 baseline 本体

Tree-Ring、Gaussian Shading、Shallow Diffuse、Stable Signature DEE 的算法本体可以通过外部 backend 接入, 但其输出必须被统一适配为 CEG records 或 baseline observations。

### 5.4 论文结果不可手工拼接

正式表格、图表、示例图 manifest、claim audit 和 result package 必须由 records 与 manifests 重建, 不允许手工拼接正式论文结果。

---

## 6. 阶段计划索引更新

更详细的阶段推进计划已经整理到:

```text
docs/builds/paper_publication_phase_plan.md
```

后续工程实施应优先以该阶段计划为主线推进, 本文档继续作为结果包契约与论文产物边界说明。
