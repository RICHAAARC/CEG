# CEG 论文发表推进阶段计划执行稿

## 0. 文档定位

本文档落盘于 `D:\Code\CEG\docs\builds`，用于把当前阶段计划整理为后续工程执行、实验排期和论文结果包验收的统一依据。整理日期为 2026-06-17。

本文档只定义推进顺序、门禁和产物契约，不声明当前项目已经完成正式论文实验。当前 `CEG` 已具备较多 dry-run、manifest、结果包和审计能力，但仍需要真实 SD / watermark / attack / detection / external baseline / advanced quality metric 结果，才能形成论文可用结果包。


---

## 0.1 2026-06-17 当前向论文推进计划快照

### 0.1.1 当前工程判断

当前 `CEG` 不应直接进入正式论文实验阶段。更合理的推进状态是:

```text
pilot_input_and_external_evidence_gate_completion
```

该阶段的含义是: 在真实 SD / watermark / attack / CEG detector / external baseline / advanced quality metric 大规模运行前, 先把所有输入、执行证据、统计口径、结果包归档和审计门禁冻结为可复核流程。该判断属于项目特定治理安排, 不是所有论文项目都必须采用的通用工程阶段名。

### 0.1.2 下一阶段主线

下一阶段主线应按以下顺序推进:

```text
1. rehearsal package 输入覆盖补齐
2. pilot_input_gap_report 复核
3. pilot_readiness_checklist 生成
4. 小规模真实 pilot 输入准备
5. 真实 CEG detector pilot
6. 至少一个 external baseline pilot
7. 真实或离线正式 advanced quality metric 导入
8. fixed-FPR / TPR@FPR 小样本统计复核
9. paper_results_package pilot 归档
10. 正式实验配置冻结
11. 正式论文实验运行
```

其中第1步和第2步仍属于工程门禁补齐, 不产生正式论文结论。第3步到第8步属于小规模 pilot, 只能用于验证流程和暴露缺口。第9步和第10步才进入可支撑论文主结果的正式实验路径。

### 0.1.3 当前最短可执行路径

为了最快向论文发表产物推进, 当前最短可执行路径是:

```text
D0: 补齐 rehearsal package 中的 detection_execution_manifest 和 experiment_matrix。
D1: 重新生成 rehearsal package 与 pilot_input_gap_report。
D2: 确认 missing_core_fields 不再包含 detection_execution_manifest / experiment_matrix。
D3: 明确剩余 gap 是否只来自 dry-run marker、formal claim gap 或真实 backend 未运行。
D4: 运行 scripts/build_pilot_readiness_checklist.py, 生成真实 pilot 启动清单。
D5: 准备小规模真实 prompt / split / seed / attack / detector 配置。
D6: 运行真实或半真实 pilot, 生成 clean / watermarked / attacked 图像和 detection events。
D7: 接入至少一个 external baseline observation 或 backend 输出。
D8: 接入 LPIPS / FID / CLIP score 中至少一种正式 metric rows。
D9: 用 pilot_input_manifest 构建 paper_results_package。
D10: 将结果包、归档包、审计报告保存到 MyDrive 分类目录。
D11: 根据 pilot 报告冻结正式实验配置。
```

### 0.1.4 MyDrive 落盘规则

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

该目录划分的主要考虑在于: 将工程变更、流程 rehearsal、小规模 pilot、正式实验和审计证据分开保存, 避免后续论文撰写时混淆 dry-run 结果与正式实验结果。

### 0.1.5 阶段门禁判定

当前阶段是否可以进入下一阶段, 应依据以下文件判断:

```text
pilot_input_gap_report.json:
  判断 pilot 输入是否仍缺少核心字段, 以及是否仍包含 dry-run marker。

pilot_readiness_checklist.json:
  把 gap 报告转换为真实 pilot 启动前的补齐任务清单。

external_result_evidence_report.json:
  判断 external baseline 或 advanced metric 是否有足够证据支撑正式声明。

paper_result_evidence_report.json:
  判断结果包中的表格、图、示例图和报告是否具备可追溯证据。

paper_readiness_report.json:
  判断 paper_results_package 是否满足 required artifacts。

paper_claim_audit.json:
  判断论文声明是否只依赖 governed records 和 manifests。
```

如果 `pilot_input_gap_report.json` 仍为 `rehearsal_or_partial_pilot_only`, 则只能继续作为 rehearsal 或 partial pilot 推进, 不能宣称已经达到 formal pilot 或 paper-ready 状态。


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
1. paper_results_package_manifest.json 能索引所有应归档文件, 包括可选的 paper_result_evidence_report.json 与 external_result_evidence_report.json。
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
4. 将 external_result_evidence_report.json 复制到 paper outputs 根目录, 并随 paper_results_package 一起归档, 便于论文结果包复核。
```

### 完成门禁

```text
1. formal_result_claim 为 true 时必须存在可解析 evidence_paths。
2. external_result_evidence_report.json 必须为 pass, 且 paper_results_package_manifest.json 的 copied_files 必须包含 external_result_evidence_report.json。
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
2. 生成 pilot_input_manifest.json；若当前还没有真实输入, 可先运行 scripts/build_pilot_rehearsal_package.py 生成 dry-run rehearsal package 验证整条构建链路。
3. 运行 pilot input preflight, 并使用 scripts/analyze_pilot_input_gap.py 生成 pilot_input_gap_report.json, 明确当前输入是 rehearsal、partial pilot 还是 ready_for_formal_pilot。
4. 运行 scripts/build_pilot_readiness_checklist.py, 将 gap 报告转换为下一批真实 pilot 输入补齐清单。
5. 如果包含外部 baseline 或高级 metric 正式声明，运行 external result evidence preflight；rehearsal 阶段只允许声明 dry_run_contract_rehearsal_not_formal_paper_result。
6. 将 external_result_evidence_report.json 纳入 paper_outputs 和 paper_results_package 归档, 并在 package manifest 中保留 copied_files 证据。
7. 用 raw builder 或 provided-results builder 构建 paper_results_package, pilot 阶段可启用 --write-paper-result-evidence-report 生成证据完整性报告。
8. 归档到 MyDrive 分类目录。
9. 检查 readiness、claim audit、package manifest、paper_result_evidence_report 和 Colab acceptance。
10. 根据 pilot_input_gap_report.json 和 pilot_readiness_checklist.json, 再启动真实 SD / watermark / attack / CEG detector / external baseline pilot。
11. pilot 通过后冻结正式实验配置。
```

---

## 6. 不应优先做的事项

```text
1. 不应先手工拼接论文表格。
2. 不应先手工挑选论文示例图并绕过 image_example_manifest.json。
3. 不应在没有 calibration / test split 的情况下统计 TPR@FPR。
4. 不应把 dry-run 图像或 mock 分数写成论文实验结论。
5. 不应在没有 external_result_evidence_report 的情况下声明外部 baseline 或高级 metric 的正式结果。
6. 不应把 scripts/build_pilot_rehearsal_package.py 生成的 rehearsal package 宣称为正式论文结果包。
7. 不应在 pilot_input_gap_report.json 仍为 rehearsal_or_partial_pilot_only 时宣称 ready_for_formal_pilot。
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
