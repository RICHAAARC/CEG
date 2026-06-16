# CEG 向论文发表推进阶段计划

## 0. 文档定位

本文档是 `D:\Code\CEG` 当前向论文发表结果包推进的阶段计划整理稿。它面向后续工程实施与论文撰写准备, 用于回答以下问题:

```text
论文发表需要哪些结果产物
这些产物应由哪些流程生成
attack 是否是必需流程
TPR@FPR 应如何统计
本地 dry-run、Colab pilot、正式实验之间如何分层
外部 baseline 应在哪个阶段接入
每个阶段的完成标准是什么
```

本文档不声明当前项目已经具备正式论文实验结果。当前 dry-run 结果只用于验证工程链路、目录契约、manifest 契约和打包流程, 不能替代真实 SD / watermark / attack / detection / baseline 实验。

---

## 1. 最终论文目标

### 1.1 最终目标

`CEG` 的最终目标是形成一个可供论文撰写和发表使用的结果包。该结果包应能直接或间接产出论文中的数据表格、统计图、标准评价指标、示例水印图像和对比 baseline 结果。

目标流程如下:

```text
prompt plan
-> clean image generation
-> watermarked image generation
-> attacked image generation
-> CEG detection
-> internal ablation detection
-> external baseline detection
-> quality and watermark metric evaluation
-> fixed-FPR threshold calibration
-> TPR@FPR / AUROC / robustness statistics
-> paper tables / figures / examples / reports
-> paper_results_package
-> colab_run_bundle
```

### 1.2 最终结果包应包含

```text
paper_results_package/
  artifacts/
    decision_summary.json
    metric_summary.json
    standard_watermark_metrics.json
    quality_metrics_summary.csv
    baseline_comparison_table.csv
    method_group_comparison_table.csv
    method_pairwise_delta_table.csv
    fixed_fpr_threshold_table.csv
    tpr_at_fixed_fpr_table.csv
    attack_tpr_at_fixed_fpr_table.csv
  latex_tables/
    *.tex
  rendered_figures/
    *.png 或 *.svg
  pdf_figures/
    *.pdf
  image_examples/
    clean/
    watermarked/
    attacked/
    comparison_grids/
    image_example_manifest.json
  image_manifests/
    image_generation_manifest.json
    image_pair_manifest.json
    attacked_image_manifest.json
    attack_shard_manifest.json
  baseline_results/
    baseline_execution_manifest.json
    baseline_observations.json
  paper_results_report.md
  paper_claim_audit.json
  paper_readiness_report.json
  paper_results_package_manifest.json
```

### 1.3 论文撰写最小可用结果

从论文发表产物角度, 最小可用结果不只是 CSV 表。至少需要以下证据链:

```text
1. 可追溯图像样本: prompt、seed、model、clean image、watermarked image。
2. 攻击样本: attacked image 及 attack 参数 provenance。
3. 检测分数: CEG、内部消融、外部 baseline 的统一记录。
4. 阈值校准: calibration clean negative 上的 fixed-FPR 阈值。
5. 测试统计: test positive / attacked positive 上的 TPR@FPR。
6. 质量指标: PSNR、SSIM、LPIPS、FID、CLIP score 等。
7. 论文图表: 表格、图、示例图、comparison grid。
8. 审计报告: manifest、readiness、claim audit、package manifest。
```

---

## 2. 当前项目状态判断

### 2.1 当前已经具备的能力

当前 `CEG` 已经具备以下论文结果包基础能力:

```text
CEG decision runtime
内部 ablation 记录结构
外部 baseline observation 适配结构
标准指标聚合结构
论文表格与 LaTeX 表重建结构
paper_results_package 导出结构
Colab dry-run 冷启动辅助结构
Colab bundle / archive / acceptance 校验结构
result index 对 required artifacts 的索引门禁
fixed-FPR / TPR@FPR 统计模块雏形
image example package 结构雏形
```

### 2.2 当前仍不应宣称具备的能力

当前不应宣称已经完成以下正式能力:

```text
真实 SD 生成正式实验图像
真实 watermark backend 生成正式水印图像
正式 attack 全量实验
正式 CEG detection 全量分数
正式外部 baseline 全量运行
正式 LPIPS / FID / CLIP score 评估
可直接支撑论文结论的全量 TPR@FPR 表
可直接支撑论文结论的全量示例图
```

### 2.3 当前阶段定位

当前阶段应定位为:

```text
工程契约与 dry-run 链路完善阶段
```

该阶段的主要目标不是追求论文数值, 而是确保真实实验一旦运行, 其产物可以被稳定、可复核地进入结果包。

---

## 3. attack 的位置与必要性

### 3.1 attack 是否必须

对于图像水印论文, attack 基本属于必需评价流程。原因如下:

```text
1. 水印方法通常需要证明在压缩、裁剪、缩放、旋转、噪声、模糊等扰动下仍可检测。
2. 若论文主张 robustness, attack 是支撑该主张的直接证据。
3. 若论文包含 geometry rescue、recover-then-content、attack robustness 等机制, attack 是验证机制有效性的必要流程。
4. 与 Tree-Ring、Gaussian Shading、Stable Signature 等外部 baseline 对比时, attack 后检测性能通常是核心比较维度。
```

因此, attack 不应作为可选后处理被忽略, 而应进入正式 paper workflow。

### 3.2 attack 不应并入图像生成阶段

推荐边界如下:

```text
图像生成阶段:
  prompt -> clean image
  prompt + watermark method -> watermarked image

attack 阶段:
  watermarked image -> attacked image

检测阶段:
  clean / watermarked / attacked image -> detection score

统计阶段:
  detection score -> threshold / TPR@FPR / robustness table
```

此处设计属于通用工程写法。生成、攻击、检测、统计分离后, 每个阶段都可以独立记录 provenance, 也便于替换 attack 算子或 baseline 方法。

### 3.3 attack 应并入哪个流程

推荐将 attack 放入 `PW03`:

```text
PW00: prompt / split / shard / experiment plan
PW01: clean and watermarked image generation
PW02: clean negative merge and fixed-FPR threshold calibration
PW03: attack shard execution
PW04: attack merge, detection metrics, quality metrics and paper tables
PW05: paper results package export
```

其中:

```text
PW03 负责产生 attacked image 和 attack manifests。
PW04 负责读取 attacked image detection scores 并统计 robustness。
PW05 负责把 attack 相关结果纳入 paper_results_package。
```

---

## 4. TPR@FPR 统计口径

### 4.1 统计原则

`TPR@FPR` 不应直接在全部样本上同时选阈值和评估。正式口径应分为 calibration 与 test:

```text
calibration clean negative -> 选择 threshold_at_fpr
test clean negative -> 复核 threshold 下的实际 FPR
test positive -> 统计 clean 或 watermarked TPR@FPR
attacked positive -> 统计 attack 条件下的 TPR@FPR
```

### 4.2 推荐目标 FPR

```text
1% FPR
0.1% FPR
```

如果样本规模不足以稳定估计 0.1% FPR, 应在报告中显式标注样本量限制, 不能把不稳定估计包装成强结论。

### 4.3 必需产物

```text
fixed_fpr_threshold_table.csv
  method_name
  target_fpr
  threshold
  calibration_negative_count
  higher_is_positive

 tpr_at_fixed_fpr_table.csv
  method_name
  target_fpr
  split
  positive_count
  true_positive_count
  tpr
  test_fpr_at_threshold

attack_tpr_at_fixed_fpr_table.csv
  method_name
  target_fpr
  attack_family
  attack_condition
  attacked_positive_count
  attacked_true_positive_count
  attacked_tpr
```

### 4.4 与 CEG-WM 的一致性要求

`D:\Code\CEG` 后续统计应与 `D:\Code\CEG-WM` 保持以下核心一致性:

```text
1. calibration clean negative 只用于阈值选择。
2. test clean negative 只用于 FPR 复核。
3. test positive 和 attacked positive 用于 TPR 统计。
4. attack_family / attack_condition 必须进入统计分组。
5. method_name、baseline_id、sample_role、split 必须保留在 records 中。
6. 表格必须由 governed records 和 manifests 重建, 不能手工拼接。
```

---

## 5. 阶段推进计划

## 阶段 1: 冻结论文结果包契约

### 目标

明确最终 paper package 必须包含哪些 artifact、manifest、table、figure 和 image example。

### 需要完成

```text
1. 更新 configs/paper_output_requirements.json。
2. 将 image_manifests、image_examples、fixed_fpr、baseline_results 纳入 required outputs。
3. 确保 paper_results_package_manifest.json 可以索引新增产物。
4. 确保 paper_readiness_report.json 可以报告缺失产物。
5. 确保 colab_paper_result_index 可以索引 required outputs。
```

### 当前状态

```text
部分完成。
fixed-FPR 表、image examples、attack manifests 的契约已经进入推进范围。
仍需持续确保 Colab dry-run 与 package validation 对新增 required outputs 一致。
```

### 完成标准

```text
dry-run package 在启用正式 readiness requirements 时通过。
缺失任一必需 manifest 时 readiness 能明确失败。
```

---

## 阶段 2: prompt 到图像样本 manifest

### 目标

让 `CEG` 能组织图像实验样本, 而不只是消费已经生成好的检测分数。

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

### 每条记录至少包含

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

### 推荐实现

```text
mock_backend:
  本地 dry-run 使用, 只生成小型测试图像或 fixture 图像。

external_backend:
  Colab / GPU 使用, 调用真实 SD 与 watermark backend, 并回收 manifest。
```

### 当前状态

```text
进行中。
本地 mock backend 已具备 prompt_plan -> clean / watermarked PPM 图像 -> image_pairs.json -> image_generation_manifest.json / image_pair_manifest.json 的轻量链路。
external backend 命令计划接口已具备, 可通过 configs/external_image_generation_command_templates.json 和 scripts/run_image_generation_plan.py 调度真实 SD / watermark 脚本并校验输出契约。
该能力已接入 dry-run 输入生成器, 用于验证 prompt provenance 和图像 manifest 契约, 但不代表正式 SD 图像生成。
```

### 完成标准

```text
本地 mock backend 可生成小样本 manifest。
Colab external backend 可接入真实图像生成脚本。
后续 attack、detection、quality metric 均可消费 image_pair_manifest.json。
```

---

## 阶段 3: attack workflow

### 目标

对 watermarked image 生成 attacked image, 并记录 attack provenance。

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

### 输入

```text
image_pair_manifest.json
attack_plan.json
```

### 输出

```text
attacked_image_manifest.json
attack_shard_manifest.json
image_pairs_attacked.json
```

### 每条记录至少包含

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

### 当前状态

```text
进行中。
本地轻量 attack workflow 已进入实现范围。
下一步重点是让 Colab dry-run pipeline 自动生成 attack manifests, 并让 build_paper_outputs.py 在正式 readiness requirements 下接收这些 manifests。
```

### 完成标准

```text
本地 dry-run 可生成 attacked image 和 attack manifests。
Colab dry-run package 中包含 attacked_image_manifest.json 与 attack_shard_manifest.json。
attack manifests 可被 detection、statistics 和 paper package 消费。
```

---

## 阶段 4: CEG detection 与内部 ablation 统一记录

### 目标

让 CEG 主方法和内部消融方法进入统一 records, 支撑主表、消融表和机制分析。

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
event_records.json
metric_summary.json
method_group_comparison_table.csv
method_pairwise_delta_table.csv
```

### 完成标准

```text
每个方法都有统一 score 字段。
每个方法都有 split、sample_role、attack_family、attack_condition。
内部消融能直接重建论文消融表。
```

---

## 阶段 5: 外部 baseline 接入

### 目标

将外部 baseline 的执行结果适配到统一 records 或 baseline observations。

### 必须纳入的 baseline

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signature DEE
```

### 输出

```text
baseline_execution_manifest.json
baseline_observations.json
baseline_comparison_table.csv
```

### 实现边界

外部 baseline 算法本体可以由外部脚本、外部仓库、Colab 环境或预生成结果产生。但是进入 `CEG` 的结果必须满足统一记录结构, 不能只保存零散日志或截图。

### 完成标准

```text
至少一个 baseline 完成 pilot 接入。
所有 baseline 均有 command plan、input manifest、output manifest。
baseline_comparison_table.csv 可由 governed records 重建。
```

---

## 阶段 6: fixed-FPR / TPR@FPR 正式统计

### 目标

对齐论文发表统计口径, 生成 clean 与 attacked 条件下的 TPR@FPR 表。

### 输入

```text
event_records.json
baseline_observations.json
threshold calibration config
```

### 输出

```text
fixed_fpr_threshold_table.csv
tpr_at_fixed_fpr_table.csv
attack_tpr_at_fixed_fpr_table.csv
对应 LaTeX 表
```

### 完成标准

```text
TPR@1%FPR 可复现。
TPR@0.1%FPR 在样本量足够时可复现。
阈值选择和测试评估严格分离。
attack TPR 按 attack_family 和 attack_condition 分组。
```

---

## 阶段 7: 图像质量指标与论文示例图

### 目标

结果包包含论文撰写可直接引用的示例图和标准图像水印指标。

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
  image_example_manifest.json
```

### 完成标准

```text
示例图文件真实存在。
示例图 manifest 可追溯到 prompt、seed、method、attack 和 detection record。
quality_metrics_summary.csv 与 standard_watermark_metrics.json 可由 records 重建。
```

---

## 阶段 8: Colab 端到端入口

### 目标

让 Notebook / Colab 从冷启动执行完整论文实验入口。

### Notebook 职责

Notebook 只负责任务调度和人机交互, 不应手写正式 records、tables、figures 或 reports。正式逻辑应放在:

```text
main/
experiments/
scripts/
paper_workflow/colab_utils/
paper_workflow/notebook_utils/
```

### 阶段步骤

```text
1. 环境准备和 Drive 挂载。
2. 检查模型、数据、baseline、HF token 或其他密钥。
3. 生成或加载 prompt plan。
4. 生成 clean / watermarked images。
5. 运行 attack shards。
6. 运行 CEG detection。
7. 运行 external baseline detection。
8. 运行 quality metrics。
9. 运行 fixed-FPR / TPR@FPR 统计。
10. 导出 paper_results_package 和 colab_run_bundle。
```

### 完成标准

```text
Colab dry-run 全链路通过。
Colab pilot 可用真实小样本输出完整 package。
正式 Colab 或 GPU 环境可输出 paper_results_package.zip。
```

---

## 阶段 9: pilot 实验

### 目标

用小规模真实实验验证链路、统计口径和 baseline 接入, 不直接作为正式论文主结果。

### 推荐规模

```text
prompt: 8 到 16
seed: 1 到 2
method: CEG + 1 到 2 个 external baseline
attack: jpeg + resize + brightness_contrast
split: calibration + test
```

### 完成标准

```text
clean / watermarked / attacked 图像真实存在。
image manifests 完整。
CEG records 完整。
至少一个 external baseline 进入 comparison table。
fixed-FPR 表可生成。
paper_results_package 可导出。
示例图可进入 image_examples。
```

---

## 阶段 10: 正式论文实验

### 目标

运行完整实验并生成论文撰写与投稿可用结果包。

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

## 6. 立即下一步计划

### 6.1 当前最优先事项

```text
1. 完成 attack workflow manifests 与 Colab dry-run pipeline 的打通。
2. 确保 attacked_image_manifest.json 和 attack_shard_manifest.json 进入 paper_results_package。
3. 确保启用 configs/paper_output_requirements.json 时 dry-run package validation 通过。
4. 继续保持 fixed-FPR / TPR@FPR 表由 records 和 manifests 重建。
```

### 6.2 随后推进事项

```text
1. prompt / image generation manifest mock backend。
2. external backend 接口, 用于真实 SD / watermark 图像生成。
3. CEG detection score producer。
4. external baseline pilot 接入。
5. quality metric runner。
6. Colab pilot 小样本正式运行。
```

### 6.3 不应优先做的事项

```text
1. 不应先手工整理论文表格。
2. 不应先手工挑选示例图并绕过 manifest。
3. 不应在没有 calibration / test split 的情况下宣称 TPR@FPR。
4. 不应在本地无 GPU dry-run 上宣称正式 SD 实验完成。
```

---

## 7. 风险与资源判断

### 7.1 本地 dry-run

本地 dry-run 应只验证:

```text
目录结构
manifest schema
命令链路
package export
readiness audit
claim audit
```

本地 dry-run 不验证真实模型性能。

### 7.2 是否需要真实 SD 模型

正式论文图像水印结果需要真实图像生成或真实外部生成结果。原因是论文需要展示和统计真实 clean / watermarked / attacked 图像, dry-run 占位图不能支撑论文结论。

### 7.3 是否需要 Hugging Face 密钥

`CEG` 项目本身不应强依赖 Hugging Face token。是否需要 token 取决于所选 SD、CLIP、LPIPS、FID 或外部 baseline backend 是否使用 gated model 或私有模型权重。

### 7.4 显存资源预估

粗略建议如下:

```text
工程 dry-run: CPU 即可。
SD 1.5 级别生成: 8GB 到 12GB GPU 显存较稳妥。
SDXL 级别生成: 16GB 到 24GB GPU 显存较稳妥。
CLIP / LPIPS / SSIM / PSNR: 通常 4GB 到 8GB GPU 或 CPU 小批量可运行。
FID: 取决于样本量, GPU 更快, CPU 可小规模验证。
多 baseline 并行正式实验: 建议 24GB 或更高显存, 或采用 shard 分批运行。
```

---

## 8. 计划执行原则

```text
1. 所有正式论文结果必须由 governed records 和 manifests 重建。
2. Notebook 只能调度, 不能成为正式逻辑唯一来源。
3. dry-run 只能证明工程链路, 不能证明论文结论。
4. attack 是鲁棒性论文结果的必要流程。
5. fixed-FPR 阈值必须由 calibration clean negative 决定。
6. external baseline 必须进入统一 records 或 baseline observations。
7. 示例图必须有 manifest 和 provenance。
8. 结果包必须可以落盘到 D:\content\drive\MyDrive\CEG 下按类型归档。
```
