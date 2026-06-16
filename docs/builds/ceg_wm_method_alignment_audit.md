# CEG 与 CEG-WM 方法机制一致性对比

## 0. 对比目标

本文档在完成 `D:\Code\CEG` 项目真实方法机制整理后, 将其与 `D:\Code\CEG-WM\doc\方法机制.md` 进行逐项对比。目标是确认当前干净仓库中的核心方法机制、formal decision、算法原语边界、消融定义、baseline 接入和产物流程是否偏离 CEG-WM 的方法机制。

对比结论分为三类:

1. **一致**: 当前 CEG 代码中已经以可执行形式实现, 且语义与 CEG-WM 方法机制一致。
2. **抽象保留**: CEG-WM 文档中定义了算法原语, 当前 CEG 未实现其数值算法本体, 但以输入字段、配置契约或外部适配边界保留其位置。
3. **范围收缩**: 当前 CEG 为清理式重构仓库, 主动移除了旧项目治理门禁、第三方算法本体和重型实验实现。该收缩不改变核心 formal decision 机制。

---

## 1. 总体结论

在当前抽取范围内, `D:\Code\CEG` 与 `D:\Code\CEG-WM\doc\方法机制.md` 的核心方法机制 **一致, 未发现 formal decision 层面的语义偏离**。

一致的核心不变量包括:

1. 内容链负责 watermark 主证据。
2. 几何链负责参考系恢复和恢复可信度评估, 不直接产生 positive。
3. 原始内容失败必须处于边界窗口, 且几何恢复可信, 才能进入 rescue。
4. 恢复后重判使用与原始内容判定相同的内容阈值。
5. Evidence-level 定义为 `positive_by_content OR positive_by_geo_rescue`。
6. Final-level 定义为 `evidence_decision AND attestation_pass`。
7. Attestation 只做最终归因约束, 不替代 watermark evidence。
8. Payload Probe 只做诊断, 不进入 formal decision。
9. Full、Content-only、Recover-then-Content、No-rescue、No-attestation 五类机制消融保持一致。
10. Tree-Ring、Gaussian Shading、Shallow Diffuse、Stable Signature DEE 均作为外部 baseline 接入。

需要特别说明的是: CEG-WM 文档中对嵌入端和提取器端的若干数值算法原语, 当前 CEG 以契约和字段方式保留, 没有实现其完整数值算法本体。这是当前 clean project 的范围收缩, 不构成 formal decision 偏离。

---

## 2. 总体架构对比

| 对比项 | CEG-WM 方法机制 | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| 方法目标 | 面向扩散生成图像的水印归因与事件级验证 | 面向同一目标, 当前实现 formal decision、协议、baseline 和产物重建 | 一致 |
| 总体结构 | 内容链 + 几何链 + 事件 attestation + payload probe | `ContentEvidence` + `GeometryEvidence` + `AttestationEvidence` + `payload_probe_score` | 一致 |
| 内容链职责 | 主内容证据与高精度主判 | `positive_by_content = content_margin_raw >= 0` | 一致 |
| 几何链职责 | 参考系恢复, 不做独立主检测 | `geometry_reliable` 只参与 rescue eligibility | 一致 |
| 事件 attestation | final-level 归因约束 | `final_decision = evidence_decision and attestation_pass` | 一致 |
| Payload Probe | 诊断 harder regime, 不进正式判定 | `payload_probe_score` 只进入 record | 一致 |
| 旧门禁 / workflow | 不属于论文方法机制 | CEG 核心方法层不读取旧门禁 | 一致且更干净 |

---

## 3. 嵌入端机制对比

| 算法原语 | CEG-WM 定义 | CEG 当前状态 | 是否偏离 |
| --- | --- | --- | --- |
| 内容自适应路由 `R` | 根据语义密度、纹理复杂度、稳定性和显著性划分区域 | 未实现数值算法; 作为方法背景和输入契约保留 | 抽象保留, 不影响判定层 |
| LF 内容分支 | 低频稳定内容证据 | 未实现嵌入端载荷; 当前只消费最终 `content_score_raw` | 抽象保留 |
| HF 内容分支 | harder regime 下的细粒度内容补充 | 未实现嵌入端载荷; 当前只消费最终内容分数 | 抽象保留 |
| 内容子空间规划 | 使用轨迹特征和 JVP 敏感性估计确定子空间 | 未实现数值规划 | 抽象保留 |
| 几何锚点嵌入 | 显式几何同步锚点 | 未实现嵌入端锚点生成; 当前消费几何诊断量 | 抽象保留 |
| 事件 attestation 构建 | 生成时建立事件级归因标识与可验证声明 | 未实现生成时构建; 当前消费 `attestation_score` | 抽象保留 |

结论: 当前 CEG 并不是完整扩散生成嵌入器实现, 而是 clean formal runtime。嵌入端原语没有被错误替换为其他机制, 也没有被几何链或 attestation 逻辑反向污染。该部分属于实现范围收缩。

---

## 4. 检测端机制对比

| 步骤 | CEG-WM 方法机制 | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| 原始内容证据提取 | 得到 `s_c^raw` | 输入为 `content_score_raw` | 抽象保留 |
| 原始内容判定 | `content_pass^raw = I(s_c^raw >= tau_c)` | `positive_by_content = content_margin_raw >= 0` | 一致 |
| 内容边界余量 | `m_c^raw = s_c^raw - tau_c` | `content_margin_raw = content_score_raw - content_threshold` | 一致 |
| 几何锚点检测 | 得到几何恢复参数 | 输入为几何诊断字段 | 抽象保留 |
| 几何可靠性 | 三项指标同时过线 | 三项指标同时过线 | 一致 |
| 恢复后内容重判 | `content_pass^align = I(s_c^align >= tau_c)` | `content_margin_aligned >= 0` | 一致 |
| Attestation 提取 | `attestation_pass = I(s_a >= tau_a)` | `attestation_score >= attestation_threshold` | 一致 |
| Payload Probe | 不进 formal decision | 不进 formal decision | 一致 |

---

## 5. 关键公式对比

### 5.1 原始内容直通

CEG-WM:

```text
positive_by_content = I(m_c^raw >= 0)
```

CEG:

```text
content_margin_raw = content_score_raw - content_threshold
positive_by_content = content_margin_raw >= 0
```

结论: 一致。

### 5.2 Rescue eligibility

CEG-WM:

```text
rescue_eligible = (
    delta_low <= m_c^raw < 0
    AND geometry_reliable
    AND fail_reason in {geometry_suspected, low_confidence}
)
```

CEG:

```text
rescue_eligible = (
    -rescue_delta_low <= content_margin_raw < 0
    and geometry_reliable
    and content_fail_reason in {geometry_suspected, low_confidence}
)
```

结论: 一致。差异只是参数符号表达方式不同。CEG-WM 将 `delta_low` 写成负下界; CEG 将 `rescue_delta_low` 写成非负窗口宽度, 使用时取负号。

### 5.3 几何救回

CEG-WM:

```text
rescue_applied = rescue_eligible AND I(m_c^align >= 0)
```

CEG:

```text
positive_by_geo_rescue = (
    rescue_eligible
    and content_margin_aligned is not None
    and content_margin_aligned >= 0
)
```

结论: 一致。CEG 额外显式处理 `content_margin_aligned is not None`, 这是工程健壮性检查, 不改变方法语义。

### 5.4 Evidence-level

CEG-WM:

```text
y_evidence = positive_by_content OR rescue_applied
```

CEG:

```text
evidence_decision = positive_by_content or positive_by_geo_rescue
```

结论: 一致。

### 5.5 Final-level

CEG-WM:

```text
y_final = y_evidence AND attestation_pass
```

CEG:

```text
final_decision = evidence_decision and attestation_pass
```

结论: 一致。

---

## 6. 几何可靠性与诊断字段对比

| 字段或概念 | CEG-WM | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| `registration_confidence` | 几何配准置信度 | 已实现 | 一致 |
| `anchor_inlier_ratio` | 锚点内点比例 | 已实现 | 一致 |
| `recovered_sync_consistency` | 恢复后同步一致性 | 已实现 | 一致 |
| `alignment_residual` | 对齐残差 | 已记录 | 一致 |
| `geometry_fail_reason` | 几何失败原因 | 已记录 | 一致 |
| `geometry_recovery_quality_bin` | 文档示例为 high / medium / low | 当前代码使用 reliable / borderline / unreliable / incomplete | 命名层差异, 非判定公式偏离 |

说明: `geometry_recovery_quality_bin` 的枚举值存在命名层差异。CEG 当前命名更偏工程可解释性: `reliable` 表示三项过线, `borderline` 表示一项低于阈值, `unreliable` 表示多项低于阈值, `incomplete` 表示必要字段缺失。该差异不影响 `geometry_reliable` 和 rescue 判定公式。如果后续要求日志枚举与 CEG-WM 文档完全一致, 可将该字段映射为 `high / medium / low` 或在文档中登记别名。

---

## 7. 状态标签对比

| 层级 | CEG-WM | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| evidence negative | `evidence_negative` | `evidence_negative` | 一致 |
| content positive | `evidence_positive_by_content` | 以 `positive_by_content=True` 表示 | 语义一致 |
| geo rescue positive | `evidence_positive_by_geo_rescue` | 以 `positive_by_geo_rescue=True` 表示 | 语义一致 |
| unattested | `evidence_positive_but_unattested` | `evidence_positive_but_unattested` | 一致 |
| final positive | `final_positive` | `final_positive` | 一致 |
| final reject | CEG-WM 文档曾列出 `final_reject`, 同时又将 final 输出分成三类 | CEG 用 `evidence_negative` 表示未成立 | 语义一致, 标签更精简 |

当前 CEG 将 evidence-level 的布尔字段与 final-level 的三分类标签同时输出。它没有单独输出 `evidence_positive_by_content` 字符串标签, 但通过 `positive_by_content=True` 可以无损恢复该状态。

---

## 8. 诊断字段对比

CEG-WM 要求输出的诊断字段如下:

```text
content_score_raw
content_score_aligned
content_margin_raw
content_margin_aligned
geometry_reliable
registration_confidence
anchor_inlier_ratio
recovered_sync_consistency
geometry_recovery_quality_bin
content_fail_reason
geometry_fail_reason
attestation_score
payload_probe_score
```

CEG 当前 `CegDecision` 已全部覆盖这些字段, 并额外输出:

```text
positive_by_content
rescue_eligible
positive_by_geo_rescue
evidence_decision
attestation_pass
final_decision
final_label
alignment_residual
geo_rescue_blocked_reason
```

结论: 字段覆盖一致且更利于机制审计。

---

## 9. 正式导出指标对比

| 指标类别 | CEG-WM 要求 | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| `final_positive_count` | 主结果统计 | 已实现 | 一致 |
| `final_negative_count` | 主结果统计 | 已实现 | 一致 |
| `TPR@FPR` | 主结果统计 | 当前实现 `tpr` 与 `clean_fpr` | 等价基础指标 |
| `clean_FPR` | 主结果统计 | `clean_fpr` | 一致 |
| `attacked_negative_FPR` | 主结果统计 | `attacked_negative_fpr` | 一致 |
| `bit_accuracy` | 主结果统计 | 当前未实现 | 范围收缩 |
| `quality_metrics` | 主结果统计 | 当前未实现真实图像质量指标 | 范围收缩 |
| `content_failed_subset_event_count` | 机制统计 | 已实现 | 一致 |
| `rescue_eligible_event_count` | 机制统计 | 已实现 | 一致 |
| `geo_rescue_applied_event_count` | 机制统计 | 已实现 | 一致 |
| `positive_by_geo_rescue_count` | 机制统计 | 已实现 | 一致 |
| `rescue_gain` | 机制统计 | 已实现 | 一致 |
| 按攻击家族统计 | rotation / scale / crop 等分层 | 当前保留 `attack_family` 与 `attack_condition`, 尚未实现专门 family gain 表 | 抽象保留 |

结论: 当前 CEG 已实现 formal decision 与 rescue 机制所需的核心聚合。图像质量、bit accuracy 和攻击家族专门表属于实验扩展层, 目前未作为核心方法包实现。

---

## 10. 方法级消融对比

| 消融版本 | CEG-WM 定义 | CEG 当前实现 | 结论 |
| --- | --- | --- | --- |
| Full | 完整方法 | `decide_ceg_event` | 一致 |
| Content-only | 仅原始内容链 | 禁用 rescue, 保留原始内容判定 | 一致 |
| Recover-then-Content | 只看恢复后内容重判 | 使用 `content_margin_aligned >= 0` | 一致 |
| No-rescue | 禁止 geometry rescue | `positive_by_geo_rescue=False` | 一致 |
| No-attestation | 去掉 final-level attestation | `attestation_pass=True` | 一致 |

结论: 消融集合和语义无偏离。

---

## 11. Baseline 对比

CEG-WM 用户目标要求外部 baseline 包括:

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
Stable Signaturedee / Stable Signature DEE
```

CEG 当前注册表包含:

```text
tree_ring -> Tree-Ring
gaussian_shading -> Gaussian Shading
shallow_diffuse -> Shallow Diffuse
stable_signature_dee -> Stable Signature DEE
```

并提供别名:

```text
tree-ring
treering
gaussian-shading
shallow-diffuse
stable-signature
stable-signature-dee
stable_signature
stable_signaturedee
```

结论: baseline 身份和接入边界一致。当前 CEG 不复制第三方算法本体, 只通过 observation 文件或 command adapter 接入外部输出。这是干净项目边界, 不是 baseline 方法偏离。

---

## 12. 产物流程对比

CEG-WM 方法机制要求正式论文表格和机制统计从 records 导出。CEG 当前实现如下:

| 产物 | CEG 当前生成方式 | 对应关系 |
| --- | --- | --- |
| `formal_final_decision_metrics.json` | `build_formal_final_decision_metrics` | final-level 主指标 |
| `content_score_distribution_audit.json` | `build_content_score_distribution_audit` | 内容分数分布审计 |
| `content_threshold_degeneracy_report.json` | `build_threshold_degeneracy_report` | 内容阈值退化检查 |
| `formal_main_table.csv` | `build_pw04_tables` | 主结果表 |
| `rescue_metrics_summary.csv` | `build_pw04_tables` | rescue 机制表 |
| `baseline_comparison_table.csv` | `build_pw04_tables` | baseline 对比表 |
| `method_group_comparison_table.csv` | `build_pw04_tables` | 主方法、内部消融和外部 baseline 分组对比表 |
| `artifact_manifest.json` | `write_artifact_bundle` | 产物摘要与 digest |

结论: 产物流程与 CEG-WM 的 records-first 原则一致。

---

## 13. 发布边界对比

CEG-WM 原项目包含更多 workflow、治理门禁和实验状态。CEG 当前 clean project 的发布边界为:

1. `minimal_method_package`: 只抽取核心方法、核心协议、配置和 README。
2. `paper_artifact_rebuild_package`: 抽取方法、分析、CLI、experiments、scripts、必要 docs 和轻量 functional tests。
3. 两个发布包均排除 `.codex`、`tools`、`audit_reports`、`outputs` 等治理或本地输出目录。

结论: 发布边界与“只抽取方法, 移除嵌入代码内部门禁”的目标一致。

---

## 14. 差异清单与判定

### 14.1 不构成偏离的范围收缩

| 差异 | 原因 | 判定 |
| --- | --- | --- |
| 未实现扩散生成嵌入端 | 当前目标是 clean formal runtime 和论文方法包抽取 | 不构成 formal decision 偏离 |
| 未实现 LF / HF carrier 数值构造 | 当前只消费内容链最终分数 | 抽象保留 |
| 未实现 JVP、路由图、真实锚点检测 | 当前只消费事件级诊断字段 | 抽象保留 |
| 未实现 bit accuracy 和真实图像质量指标 | 当前未引入真实大规模实验输出 | 范围收缩 |
| 未复制第三方 baseline 算法 | 避免外部算法污染核心方法层 | 边界正确 |

### 14.2 需要持续关注的非核心命名差异

| 差异 | 当前影响 | 建议 |
| --- | --- | --- |
| `geometry_recovery_quality_bin` 枚举值不同 | 不影响 `geometry_reliable` 和 rescue 判定 | 若论文日志要求严格复现 CEG-WM 文档, 增加 high / medium / low 映射 |
| `final_reject` 未作为单独 label 输出 | 可由 `final_decision=False` 和 `final_label` 恢复语义 | 若需要兼容旧日志, 可在导出层增加 alias |
| `evidence_positive_by_content` 未作为字符串 label 输出 | 由 `positive_by_content=True` 表示 | 若需要兼容旧表, 可在导出层派生 |

这些差异是日志表示或导出表示差异, 不是算法核心偏离。

---

## 15. 最终一致性判断

按核心方法机制和算法原语边界判断:

```text
内容链主证据: 一致
几何链参考系恢复: 一致
几何链不直接 positive: 一致
边界失败 rescue: 一致
恢复后同阈值重判: 一致
Evidence-level: 一致
Attestation final constraint: 一致
Payload Probe diagnostic only: 一致
机制消融: 一致
外部 baseline 身份: 一致
records-first 产物重建: 一致
最小方法包边界: 一致
```

因此, 当前 `D:\Code\CEG` 在已经实现的 clean project 范围内, 与 `D:\Code\CEG-WM\doc\方法机制.md` 的核心方法机制保持一致, 未发现 formal decision 层面的无意偏离。

如果后续目标从“清理式方法抽取”升级为“完整扩散生成水印算法实现”, 则还需要补齐以下可执行算法模块:

1. 内容自适应路由。
2. LF / HF 内容链嵌入与提取。
3. JVP 敏感性估计。
4. 几何锚点嵌入、检测和逆变换恢复。
5. Attestation 构建与提取器。
6. Payload Probe 提取器。
7. bit accuracy 与图像质量指标。
8. 按攻击家族的正式分层统计表。
