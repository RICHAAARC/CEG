# CEG 项目方法机制整理

## 0. 文档定位

本文档根据 `D:\Code\CEG` 当前真实代码、配置、测试和发布边界整理 CEG 项目的方法机制。本文档不是从旧项目复制的说明, 而是以当前干净仓库中已经落地的模块为事实来源。

事实来源包括:

```text
main/methods/ceg/decision.py
main/methods/ceg/ablations.py
main/methods/baselines.py
main/methods/baseline_adapters.py
main/protocol/experiment.py
main/protocol/runtime.py
main/analysis/aggregation.py
main/analysis/rebuild_artifacts.py
experiments/protocol_runner.py
experiments/baseline_file_adapter.py
experiments/baseline_command_adapter.py
configs/ceg_method_contract.yaml
configs/baseline_registry.yaml
configs/paper_main_*.yaml
configs/paper_mechanism_*.yaml
scripts/build_release_package.py
scripts/extract_minimal_paper_package.py
```

当前 `D:\Code\CEG` 的方法实现重点是: **抽取 CEG 的 formal decision、机制消融、实验协议、baseline 接入、结果聚合和论文产物重建流程**。它没有把旧项目的内部治理门禁、workflow 门禁、运行时白名单或审计工具嵌入方法层。

---

## 1. 项目级方法目标

CEG 当前项目实现的是一个面向扩散生成图像水印归因的双链判定框架。它将方法职责拆成以下层级:

1. **内容链**: 负责 watermark 主证据, 即在原始坐标系中给出内容证据分数 `content_score_raw`, 并在几何恢复坐标系中给出重判分数 `content_score_aligned`。
2. **几何链**: 负责参考系恢复可信度, 即通过 `registration_confidence`、`anchor_inlier_ratio`、`recovered_sync_consistency` 等指标判断是否可以相信恢复后的坐标系。几何链不直接产生 positive 判定。
3. **恢复后内容重判**: 当原始内容证据处于边界失败区间, 且几何恢复可信时, 使用同一个内容阈值重新判断恢复后内容分数。
4. **事件级 attestation**: 负责 final-level 归因约束。它不能替代 watermark evidence, 只能在 evidence-level 成立后决定是否输出最终归因成立。
5. **Payload Probe**: 只作为诊断字段记录 `payload_probe_score`, 不进入 formal decision。

这一分层属于项目特定设计。通用工程写法是把输入证据、阈值、判定结果和聚合流程拆成显式数据结构; 项目特定设计是双链机制、几何救回规则和 evidence-level / final-level 的分层归因语义。

---

## 2. 当前代码中的核心数据结构

### 2.1 `CegThresholds`

`CegThresholds` 位于 `main/methods/ceg/decision.py`, 表示 CEG formal decision 所需的最小阈值集合。

字段如下:

| 字段 | 含义 | 默认值 | 机制角色 |
| --- | --- | --- | --- |
| `content_threshold` | 内容链原始判定与恢复后重判共用阈值 | 无默认值 | 主证据阈值 |
| `attestation_threshold` | 事件级 attestation 阈值 | 无默认值 | final-level 约束 |
| `registration_confidence_min` | 几何配准置信度最小值 | `0.3` | 几何可靠性门槛 |
| `anchor_inlier_ratio_min` | 锚点内点比例最小值 | `0.5` | 几何可靠性门槛 |
| `recovered_sync_consistency_min` | 恢复后同步一致性最小值 | `0.55` | 几何可靠性门槛 |
| `rescue_delta_low` | 原始内容边界失败窗口宽度 | `0.05` | rescue eligibility |

注意: 当前 CEG 代码中 `rescue_delta_low` 是非负窗口宽度。公式中使用 `-rescue_delta_low <= content_margin_raw < 0`。这与旧方法文档中的 `delta_low <= m_c^raw < 0` 等价, 其中 `delta_low` 是负数。

### 2.2 `ContentEvidence`

`ContentEvidence` 表示内容链证据。

| 字段 | 含义 | 是否进入 formal decision |
| --- | --- | --- |
| `content_score_raw` | 原始坐标系内容链分数 | 是 |
| `content_score_aligned` | 几何恢复后坐标系内容链重判分数 | 仅在 rescue 中使用 |
| `content_fail_reason` | 原始内容失败原因 | 影响 rescue eligibility |
| `payload_probe_score` | bit-level 或 harder regime 诊断分数 | 否, 只记录 |

允许进入 rescue 的失败原因固定为:

```text
geometry_suspected
low_confidence
```

这对应“几何失配可疑”或“低置信边界失败”的样本, 不对所有内容失败样本无差别开放救回。

### 2.3 `GeometryEvidence`

`GeometryEvidence` 表示几何链恢复证据。

| 字段 | 含义 | 机制角色 |
| --- | --- | --- |
| `registration_confidence` | 参考系配准置信度 | 几何可靠性判定 |
| `anchor_inlier_ratio` | 几何锚点内点比例 | 几何可靠性判定 |
| `recovered_sync_consistency` | 恢复后同步一致性 | 几何可靠性判定 |
| `alignment_residual` | 对齐残差 | 诊断字段 |
| `geometry_fail_reason` | 几何失败原因 | 诊断字段 |

几何链只决定 `geometry_reliable`, 不直接设置 `final_decision=True`。这是 CEG 的关键方法边界。

### 2.4 `AttestationEvidence`

`AttestationEvidence` 只包含:

```text
attestation_score
```

其判定规则为:

```text
attestation_pass = attestation_score >= attestation_threshold
```

该分支只影响 final-level, 不影响 evidence-level 的 watermark 主证据是否成立。

### 2.5 `CegDecision`

`CegDecision` 是单事件 formal decision 的扁平化结果, 也是后续 records 和聚合器消费的主要字段来源。核心字段包括:

```text
positive_by_content
rescue_eligible
positive_by_geo_rescue
evidence_decision
attestation_pass
final_decision
final_label
content_score_raw
content_score_aligned
content_margin_raw
content_margin_aligned
geometry_reliable
registration_confidence
anchor_inlier_ratio
recovered_sync_consistency
alignment_residual
geometry_recovery_quality_bin
content_fail_reason
geometry_fail_reason
attestation_score
payload_probe_score
geo_rescue_blocked_reason
```

该结构属于通用工程写法与项目特定写法的结合: 使用扁平 record 便于 CSV / JSONL / 聚合器消费属于通用工程写法; 字段语义和 rescue 诊断属于 CEG 项目特定写法。

---

## 3. Formal decision 算法流程

### 3.1 数值合法性检查

所有关键输入分数都会经过 `_finite_float` 检查。该检查要求输入是有限数字, 拒绝 `NaN`、无穷值、布尔值和非数值对象。

这是通用工程写法, 作用是让判定逻辑 fail-fast, 避免无效数值进入论文 records。

### 3.2 原始内容判定

首先计算原始内容边界余量:

```text
content_margin_raw = content_score_raw - content_threshold
```

原始内容直通判定为:

```text
positive_by_content = content_margin_raw >= 0
```

该规则对应 CEG-WM 方法机制中的:

```text
positive_by_content = I(m_c^raw >= 0)
```

### 3.3 几何恢复可信度判定

`evaluate_geometry_reliability` 使用三项几何指标判断参考系恢复是否可信:

```text
registration_confidence >= registration_confidence_min
anchor_inlier_ratio >= anchor_inlier_ratio_min
recovered_sync_consistency >= recovered_sync_consistency_min
```

三项全部过线时:

```text
geometry_reliable = True
```

任一指标缺失或低于阈值时:

```text
geometry_reliable = False
```

当前实现还输出 `geometry_recovery_quality_bin` 和失败原因, 用于解释几何链为什么不能参与 rescue。

### 3.4 恢复后内容边界余量

如果存在 `content_score_aligned`, 则计算:

```text
content_margin_aligned = content_score_aligned - content_threshold
```

这里明确复用同一个 `content_threshold`, 不为恢复后重判引入新的内容阈值。这一点是 CEG 方法的核心约束之一。

### 3.5 Rescue 候选条件

当前 CEG 代码中的 rescue eligibility 为:

```text
rescue_eligible = (
    -rescue_delta_low <= content_margin_raw < 0
    and geometry_reliable
    and content_fail_reason in {geometry_suspected, low_confidence}
)
```

含义如下:

1. 原始内容链没有通过, 但只是在边界附近失败。
2. 几何链恢复可信。
3. 内容失败原因必须是可救回原因, 即 `geometry_suspected` 或 `low_confidence`。

这保证 rescue 只用于“更可能由几何失配造成的边界失败样本”, 而不是让几何链成为第二个独立检测器。

### 3.6 几何救回成立条件

真正的几何救回判定为:

```text
positive_by_geo_rescue = (
    rescue_eligible
    and content_margin_aligned is not None
    and content_margin_aligned >= 0
)
```

这表示几何链本身不判 positive。几何链只把样本送回恢复坐标系, 最终仍由内容链以同一内容阈值重判。

### 3.7 Evidence-level 判定

Evidence-level 的 watermark 主证据为:

```text
evidence_decision = positive_by_content or positive_by_geo_rescue
```

该层只回答 watermark evidence 是否成立, 不回答最终事件归因是否成立。

### 3.8 Attestation-level 与 Final-level 判定

Attestation 判定为:

```text
attestation_pass = attestation_score >= attestation_threshold
```

最终判定为:

```text
final_decision = evidence_decision and attestation_pass
```

离散标签为:

| 条件 | `final_label` |
| --- | --- |
| `final_decision=True` | `final_positive` |
| `evidence_decision=True` 且 `attestation_pass=False` | `evidence_positive_but_unattested` |
| `evidence_decision=False` | `evidence_negative` |

该设计严格区分 watermark 主证据与事件级归因一致性。

### 3.9 Rescue 阻断原因

当 rescue 没有成立时, 当前代码输出 `geo_rescue_blocked_reason`。可能值包括:

```text
outside_rescue_band
geometry_gate_failed
content_fail_reason_not_rescuable
missing_aligned_content_score
aligned_content_below_threshold
```

这些字段不改变 final decision, 只用于机制分析和失败模式解释。

---

## 4. CEG 机制消融

机制消融位于 `main/methods/ceg/ablations.py`。当前支持五个版本:

```text
Full
Content-only
Recover-then-Content
No-rescue
No-attestation
```

### 4.1 Full

完整 CEG 方法, 包含:

1. 原始内容链直通判定。
2. 几何恢复可信度判定。
3. 边界失败样本的恢复后内容重判。
4. 事件级 attestation 约束。

### 4.2 Content-only

仅保留:

```text
positive_by_content = content_margin_raw >= 0
```

禁用 rescue, 但仍保留 attestation 作为 final-level 约束。该版本用于量化原始内容链自身能力。

### 4.3 Recover-then-Content

该版本只看恢复后内容重判:

```text
positive_by_recovered_content = content_margin_aligned >= 0
```

它不保留原始内容直通分支, 用于分析恢复坐标系中的内容判定本身是否有效。

### 4.4 No-rescue

该版本保留完整诊断字段和几何可靠性输出, 但禁止 `positive_by_geo_rescue=True`。其 evidence-level 退化为:

```text
evidence_decision = positive_by_content
```

该版本用于量化显式 rescue 规则的独立贡献。

### 4.5 No-attestation

该版本保留完整 evidence-level, 但强制 final-level 不再受 attestation 阈值约束:

```text
attestation_pass = True
final_decision = evidence_decision
```

该版本用于分析 attestation 对误报约束的作用。

---

## 5. 事件协议与运行时数据流

### 5.1 事件输入结构

`EventProtocolRecord` 位于 `main/protocol/experiment.py`, 是 CEG 和 baseline 共用的事件级输入协议。

字段包括:

```text
event_id
method_name
split
sample_role
attack_family
attack_condition
is_watermarked
payload
```

其中 `payload` 按约定包含:

```text
payload.thresholds
payload.content
payload.geometry
payload.attestation
payload.ceg_ablation_variants
payload.baseline_observations
```

### 5.2 CEG 运行时转换

`main/protocol/runtime.py` 中的 `_build_ceg_inputs` 将 `payload` 显式转换为:

```text
ContentEvidence
GeometryEvidence
AttestationEvidence
CegThresholds
```

随后 `run_ceg_event` 调用 `decide_ceg_event` 并输出统一 record。

### 5.3 消融运行时转换

`run_ceg_ablation_events` 从 `payload.ceg_ablation_variants` 读取变体名称, 对每个变体调用 `decide_ceg_ablation_event`, 输出 `method_name` 形如:

```text
ceg_full
ceg_content_only
ceg_recover_then_content
ceg_no_rescue
ceg_no_attestation
```

### 5.4 Baseline 运行时转换

`run_baseline_events` 从 `payload.baseline_observations` 读取外部 baseline 输出, 并使用 `adapt_baseline_observation` 转成统一 record。

统一运行入口为:

```text
run_protocol_events(events)
```

该函数对每个事件依次输出:

1. CEG full record。
2. CEG ablation records。
3. 外部 baseline records。

---

## 6. 外部 baseline 机制

### 6.1 Baseline 注册表

当前 baseline 注册表位于 `main/methods/baselines.py` 和 `configs/baseline_registry.yaml`。

已注册的外部对照方法包括:

| `baseline_id` | 展示名 | 角色 |
| --- | --- | --- |
| `tree_ring` | Tree-Ring | external main table |
| `gaussian_shading` | Gaussian Shading | external main table |
| `shallow_diffuse` | Shallow Diffuse | external main table |
| `stable_signature_dee` | Stable Signature DEE | external main table |

当前项目还提供 baseline 别名规范化, 例如 `tree-ring` 会映射到 `tree_ring`, `stable_signaturedee` 会映射到 `stable_signature_dee`。

### 6.2 Baseline 适配器

`BaselineObservation` 是外部 baseline 的最小输入契约:

```text
baseline_id
score
threshold
score_name
higher_is_positive
metadata
```

`adapt_baseline_observation` 的核心规则为:

```text
final_decision = score >= threshold
```

如果 `higher_is_positive=False`, 则使用:

```text
final_decision = score <= threshold
```

baseline record 不包含 CEG 专属的几何救回字段。因此在聚合阶段, baseline 的 rescue 相关统计自然为 0, 不会与 CEG 内部机制混淆。

### 6.3 Baseline 文件与命令接入

当前项目提供两类接入方式:

1. `experiments/baseline_file_adapter.py`: 从 JSON、JSONL 或 CSV 读取 baseline observation rows。
2. `experiments/baseline_command_adapter.py`: 执行外部 baseline 命令, 再读取其输出 observation 文件。

这两个模块都位于 `experiments/`, 不污染 `main/methods/ceg/`。这是一种通用工程边界设计: 第三方算法实现作为外部系统接入, 核心方法层只消费标准化 observation。

---

## 7. Profile 与实验协议

当前激活 profile 包括:

```text
paper_main_probe
paper_main_pilot
paper_main_full
paper_mechanism_geo_search
paper_mechanism_quickcheck
paper_mechanism_pilot
```

### 7.1 paper main profile

`paper_main_probe`、`paper_main_pilot`、`paper_main_full` 用于主线结果验证。它们默认包含:

```text
sample_roles:
  positive_source
  clean_negative
splits:
  dev
  calibration
  test
threshold_split: calibration
formal_report_split: test
external_baselines:
  tree_ring
  gaussian_shading
  shallow_diffuse
  stable_signature_dee
```

### 7.2 paper mechanism profile

`paper_mechanism_geo_search`、`paper_mechanism_quickcheck`、`paper_mechanism_pilot` 用于机制分析。它们在主线协议基础上增加消融计划:

```text
Full
Content-only
Recover-then-Content
No-rescue
No-attestation
```

### 7.3 阈值原则

当前配置中的默认阈值为:

```text
content_threshold: 0.5
attestation_threshold: 0.5
registration_confidence_min: 0.3
anchor_inlier_ratio_min: 0.5
recovered_sync_consistency_min: 0.55
rescue_delta_low: 0.05
```

这些阈值是协议占位级默认值, 正式论文实验应在 `calibration` split 中校准, 不应在 `test` split 上回调。

---

## 8. 结果聚合机制

`main/analysis/aggregation.py` 按 `method_name` 聚合统一 records。核心统计包括:

| 指标 | 定义 |
| --- | --- |
| `event_count` | 方法对应事件记录数 |
| `final_positive_count` | `final_decision=True` 的记录数 |
| `final_negative_count` | 总数减去 final positive 数 |
| `tpr` | `positive_source` 中 final positive 比例 |
| `clean_fpr` | `clean_negative` 中 final positive 比例 |
| `attacked_negative_fpr` | `attacked_negative` 中 final positive 比例 |
| `content_failed_subset_event_count` | positive source 中 content-only 未通过的事件数 |
| `rescue_eligible_event_count` | `rescue_eligible=True` 的事件数 |
| `geo_rescue_applied_event_count` | `positive_by_geo_rescue=True` 的事件数 |
| `positive_by_content_count` | 原始内容直通过线事件数 |
| `positive_by_geo_rescue_count` | 几何救回过线事件数 |
| `rescue_gain` | `final_positive_count - positive_by_content_count` |

需要注意: 对 baseline records, 因为没有 CEG 专属机制字段, `positive_by_content`、`positive_by_geo_rescue` 和 `rescue_eligible` 会按 False 处理。这保证 baseline 只参与主结果比较, 不参与 CEG 内部 rescue 机制解释。

---

## 9. 论文产物重建机制

`main/analysis/rebuild_artifacts.py` 从 records 重建 PW02 / PW04 等价产物。

### 9.1 PW02 等价产物

```text
formal_final_decision_metrics.json
content_score_distribution_audit.json
content_threshold_degeneracy_report.json
```

其中:

1. `formal_final_decision_metrics.json` 汇总 final-level 主指标。
2. `content_score_distribution_audit.json` 按 method / sample_role 汇总 `content_score_raw` 分布。
3. `content_threshold_degeneracy_report.json` 检查 clean-side 和 positive-side 内容分数是否存在退化或重叠。

### 9.2 PW04 等价表格

```text
formal_main_table.csv
rescue_metrics_summary.csv
baseline_comparison_table.csv
method_group_comparison_table.csv
```

其中:

1. `formal_main_table.csv` 保存主表所需的 TPR、clean FPR、attacked negative FPR 和 final positive / negative counts。
2. `rescue_metrics_summary.csv` 保存 CEG rescue 机制分析字段。
3. `baseline_comparison_table.csv` 保存 CEG 与外部 baseline 的主结果比较。
4. `method_group_comparison_table.csv` 显式标注 CEG 主方法、内部消融和外部 baseline 的分组职责, 避免论文对比表混淆不同实验角色。

### 9.3 Artifact manifest

`write_artifact_bundle` 写出 JSON / CSV 产物后会生成 `artifact_manifest.json`, 其中包含:

```text
manifest_name
artifact_names
artifact_digest
```

这保证产物可以由 records 和代码重建, 而不是手工拼接。

---

## 10. CLI 与 Notebook 边界

当前正式 CLI 为:

```text
python -m main.cli.run_paper_protocol
```

该 CLI 从事件 JSON 和阈值 JSON 读取输入, 输出:

```text
event_records.json
protocol_summary.json
artifacts/artifact_manifest.json
artifacts/formal_final_decision_metrics.json
artifacts/content_score_distribution_audit.json
artifacts/content_threshold_degeneracy_report.json
artifacts/formal_main_table.csv
artifacts/rescue_metrics_summary.csv
artifacts/baseline_comparison_table.csv
artifacts/method_group_comparison_table.csv
```

带 baseline 文件的脚本入口为:

```text
python scripts/run_paper_protocol_with_baseline_file.py
```

Notebook 边界由 `paper_workflow/notebook_utils/protocol_entrypoint.py` 提供。Notebook 只应调用 repository modules, 不应直接手写正式 records、tables 或 reports。

---

## 11. 最小发布包机制

当前项目提供两个可执行抽取 profile:

### 11.1 `minimal_method_package`

该包包含:

```text
main/core
main/methods
main/protocol
configs
README.md
pyproject.toml
```

该包排除:

```text
.codex
tools
tests
experiments
scripts
paper_workflow
audit_reports
outputs
__pycache__
.pytest_cache
```

目的: 发布最小 CEG 方法核心, 保证 `main.methods.ceg` 可以独立导入和运行 `decide_ceg_event`。

### 11.2 `paper_artifact_rebuild_package`

该包包含方法、协议、实验 runner、脚本、必要文档和轻量功能测试, 用于重建论文产物。

它仍排除治理层、审计层、本地输出和集成测试。

---

## 12. 当前 CEG 项目没有实现的部分

为了避免误解, 需要明确当前 `D:\Code\CEG` 与完整论文方法描述之间的实现边界。

当前 CEG 已经实现:

1. formal decision。
2. geometry rescue 判定规则。
3. evidence-level / final-level 分层。
4. attestation final constraint。
5. payload probe 诊断字段的记录。
6. 机制消融。
7. baseline 接入契约。
8. records 聚合。
9. PW02 / PW04 等价产物重建。
10. 最小方法发布包抽取。

当前 CEG 没有实现:

1. 扩散生成过程中的真实内容链嵌入。
2. LF / HF 内容 carrier 的数值构造。
3. 内容自适应路由图 `R` 的真实计算。
4. JVP 敏感性估计。
5. 真实几何锚点嵌入和提取。
6. 真实逆几何变换 `W(y; T^-1)`。
7. 真实 attestation 提取器。
8. 真实 payload probe 提取器。
9. Tree-Ring、Gaussian Shading、Shallow Diffuse、Stable Signature DEE 的第三方算法本体。

这些未实现部分在当前 clean project 中被保留为 **方法契约、输入字段和外部适配边界**。这属于当前清理式重构目标下的实现范围收缩, 不是 formal decision 机制的反向偏离。

---

## 13. 方法机制总结

当前 CEG 项目的真实方法链路可以概括为:

```text
事件 payload
-> ContentEvidence / GeometryEvidence / AttestationEvidence / CegThresholds
-> 原始内容边界余量 content_margin_raw
-> positive_by_content
-> 几何三指标可靠性判断 geometry_reliable
-> 恢复后内容边界余量 content_margin_aligned
-> rescue_eligible
-> positive_by_geo_rescue
-> evidence_decision
-> attestation_pass
-> final_decision / final_label
-> event record
-> aggregate_decision_rows
-> PW02 / PW04 artifact rebuild
-> release extraction
```

核心不变量如下:

1. 内容链是主证据。
2. 几何链只恢复参考系, 不直接判 positive。
3. rescue 只对边界失败且几何可信的样本开放。
4. 恢复后重判使用同一个内容阈值。
5. Attestation 只约束 final-level, 不替代 evidence-level。
6. Payload probe 只诊断, 不进入 formal decision。
7. Baseline 通过 observation 适配进入 records, 不污染 CEG 内部机制。
8. 论文产物由 records 和 manifest 重建, 不手工拼接。


---

## 13. Supported claims 审计机制

当前 `D:\Code\CEG` 还包含 `main/analysis/claim_audit.py`, 用于把论文中可陈述的核心结论显式绑定到受治理产物。该机制不改变 CEG formal decision, 只在 artifact rebuild 层检查以下关系:

1. formal detection performance 必须由 `formal_final_decision_metrics.json` 和 `formal_main_table.csv` 支撑。
2. 内部机制消融比较必须由 `rescue_metrics_summary.csv`、`method_group_comparison_table.csv` 和 `method_pairwise_delta_table.csv` 支撑。
3. 外部 baseline 比较必须覆盖 Tree-Ring、Gaussian Shading、Shallow Diffuse 和 Stable Signature DEE, 并由 `baseline_comparison_table.csv` 与 `method_group_comparison_table.csv` 等产物支撑。
4. 图像水印标准指标必须由 `standard_watermark_metrics.json`、`quality_metrics_summary.csv`、`bit_recovery_metrics.csv` 和 `attack_family_metrics.csv` 支撑。
5. 检测曲线、score 分布、operating point 和不确定性必须由对应 CSV 表格支撑。
6. 论文核心图必须在 `paper_figure_specs.json` 中具备稳定 `figure_id`。

这一实现属于通用工程治理写法: 它把“论文声明是否有证据”从人工检查转化为可重复执行的 JSON 审计。项目特定部分在于 claim contract 的内容与 CEG 论文产物集合绑定。


---

## 14. 论文结果输出包导出机制

当前项目通过 `main/analysis/result_package.py` 和 `scripts/export_paper_results_package.py` 提供论文结果输出包导出能力。该机制的输入是 `scripts/build_paper_outputs.py` 已经生成并通过 readiness 的输出目录, 输出是独立的 `paper_results_package` 目录。

该结果包包含:

1. `event_records.json`, 即所有表格、图表和报告的事实来源。
2. `artifacts/` 下的 JSON / CSV 指标产物, 包括标准水印指标、baseline、消融、不确定性、检测曲线和 claim audit。
3. `rendered_figures/` 下的 SVG 与 HTML 图表报告。
4. `latex_tables/` 下的 LaTeX 表格。
5. `pdf_figures/` 下的 PDF 图表预览。
6. `paper_results_report.md` 与对应 manifest。
7. `paper_results_package_manifest.json`, 用于记录每个文件的 `relative_path`、`byte_count` 和 `sha256`。

这一实现属于通用工程写法: 用 manifest 和文件 digest 确保结果包可审计、可复制、可校验。项目特定写法在于结果包必须同时记录 `readiness_decision` 和 `claim_audit_decision`, 以防止未通过论文产物完整性检查或 claim 支撑检查的目录被误当作正式结果包。
