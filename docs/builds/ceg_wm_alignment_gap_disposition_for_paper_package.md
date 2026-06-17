# CEG 与 CEG-WM 方法差距的论文结果包处置判定

## 1. 文档目的

本文档基于 `docs/builds/ceg_wm_method_alignment_audit.md` 与 `docs/builds/paper_publication_result_package_requirements.md`, 专门回答以下问题:

1. `D:\Code\CEG` 中哪些“未实现”或“抽象保留”内容, 按顶会论文结果包要求必须补成实际代码或实际参数。
2. 哪些 CEG-WM 遗留机制、字段或工程结构, 对论文结果包非必要, 不应继续保留在 CEG 项目核心路径中。
3. 哪些地方虽然与 CEG-WM 存在差异, 但当前 `D:\Code\CEG` 的设计更合理, 应作为正式项目方向保留。

本文档不是实验结果, 也不声称当前 CEG 已经满足正式论文主方法运行要求。它的作用是给后续实现排序, 避免继续把“抽象保留”误认为“顶会论文可用能力”。

## 2. 判定原则

面向顶会论文结果包, 判断一个机制是否必须实现, 不能只看它是否出现在 CEG-WM 原项目中, 而应看它是否支撑以下论文产物:

1. 真实 clean / watermarked / attacked 图像。
2. 可复核 detection records。
3. fixed-FPR 统计, 包括阈值、TPR、empirical FPR 和置信区间。
4. baseline 同口径对比。
5. 图像质量指标。
6. 消融实验。
7. 论文图表和 supported claims。
8. 可由 records 与 manifests 重建的结果包。

因此, 本文档采用三类处置结论:

| 结论 | 含义 |
|---|---|
| 必须补实际代码或参数 | 若不实现, 就不能支撑正式论文主结果或核心结论 |
| 非必要, 不应保留在核心路径 | 对顶会结果包没有直接贡献, 或属于旧项目治理 / workflow 噪声 |
| CEG 差异更合理 | 与 CEG-WM 不完全一致, 但更适合 clean project、可复现结果包或长期维护 |

## 3. 必须补实际代码或参数的内容

### 3.1 正式图像水印嵌入 backend

当前状态:

- `ceg_wm_method_alignment_audit.md` 中 LF / HF carrier、内容自适应路由、子空间规划、几何锚点、attestation 构建等内容多为“抽象保留”。
- 当前 `scripts/run_pilot_real_image_generation_backend.py` 中的 `ceg_native_lsb` 只能视为流程联调级水印原语, 不能作为论文主方法水印。

论文结果包判定:

```text
必须补实际代码。
```

原因:

1. 论文主方法必须真实产生 watermarked 图像。
2. watermarked 图像必须来自与方法设计一致的水印机制。
3. 如果只使用 `ceg_native_lsb`, 只能证明流程能跑通, 不能支撑 CEG 方法主张。

应补内容:

```text
main/watermarking/
  semantic_mask.py
  subspace_planner.py
  content_lf.py
  content_hf.py
  geometry_sync.py
  attestation.py
  embedding_pipeline.py
```

至少需要的正式参数:

| 参数 | 作用 |
|---|---|
| `model_id` | 指定 SD 或等价生成模型 |
| `seed` | 控制图像生成可复现性 |
| `watermark_message_length` | 控制 payload / watermark bit 长度 |
| `lf_strength` | 控制低频水印嵌入强度 |
| `hf_strength` | 控制高频水印嵌入强度 |
| `subspace_rank` | 控制子空间维度 |
| `timestep_start` / `timestep_end` | 控制扩散轨迹注入区间 |
| `semantic_mask_backend` | 指定 mask 来源, 如 InSPyReNet 或等价实现 |
| `attestation_key_id` | 标识事件级归因密钥或等价证明材料 |

### 3.2 InSPyReNet / semantic mask 或等价 semantic mask backend

当前状态:

- CEG-WM 方法机制中 semantic mask / saliency mask 是水印路由和区域选择的重要机制。
- 当前 CEG 仅在需求文档和消融项中保留 `No semantic mask`、`No InSPyReNet mask` 等位置, 尚无正式可运行 mask backend。

论文结果包判定:

```text
若论文主方法声称使用 semantic-aware 或 saliency-aware watermark, 则必须补实际代码和参数。
```

原因:

1. 论文流程图中若出现 `semantic mask / InSPyReNet`, 结果包必须有对应运行记录。
2. 消融表若报告 `No InSPyReNet mask`, 则 Full 方法必须真实使用该模块。
3. 图像质量和鲁棒性结论通常依赖 mask 对可见区域、纹理区域或稳定区域的选择。

应补内容:

```text
main/watermarking/semantic_mask.py
configs/watermark_config.yaml 或 configs/watermark_config.json
```

必须记录的参数:

| 参数 | 作用 |
|---|---|
| `semantic_mask_backend` | mask 后端名称 |
| `semantic_model_id` 或 `semantic_model_path` | 模型来源 |
| `mask_threshold` | 二值化或软 mask 门限 |
| `mask_postprocess` | 膨胀、腐蚀、平滑等后处理策略 |
| `mask_usage` | 用于 LF、HF、geometry 或全部分支 |

如果后续决定不用 InSPyReNet, 则必须在论文方法中删除相关主张, 并删除 `No InSPyReNet mask` 这类消融要求。

### 3.3 LF / HF 内容链实现

当前状态:

- CEG 当前 formal decision 消费的是 `content_score_raw` 和 `content_score_aligned`。
- 但真实生成和检测这些分数的 LF / HF 内容链尚未在 CEG 中完整实现。

论文结果包判定:

```text
必须补实际代码。
```

原因:

1. `content_score_raw` 是主检测证据来源。
2. 没有真实内容链, TPR@FPR 只能来自模拟分数或外部 records, 不能支撑主方法。
3. LF / HF 若出现在方法图、消融表或结论中, 必须能产生 records。

应补内容:

```text
main/watermarking/content_chain/
  low_freq_embedder.py
  low_freq_detector.py
  high_freq_embedder.py
  high_freq_detector.py
  content_score_fusion.py
```

必须记录的参数:

| 参数 | 作用 |
|---|---|
| `lf_enabled` / `hf_enabled` | 是否启用对应分支 |
| `lf_ecc` | 低频链纠错编码方式 |
| `lf_variance` | 低频扰动或模板强度 |
| `hf_selection` | 高频区域选择策略 |
| `hf_tau` | 高频门限或选择温度 |
| `content_threshold` | 内容链 detection operating point |

### 3.4 子空间规划与扩散轨迹相关原语

当前状态:

- CEG-WM 中存在 JVP、trajectory tap、subspace planner 等机制。
- CEG 当前没有真实扩散轨迹子空间规划实现。

论文结果包判定:

```text
如果论文方法声称使用 latent / trajectory / subspace watermark, 必须补实际代码和参数。
```

原因:

1. 这是区分普通像素水印和扩散模型水印的重要方法贡献。
2. 若不实现, 论文主方法不能声称使用 diffusion trajectory 或 latent subspace。
3. 该模块直接影响生成阶段 provenance、检测分数和消融实验。

应补内容:

```text
main/watermarking/subspace/
  trajectory_capture.py
  jvp_sensitivity.py
  subspace_planner.py
  latent_modifier.py
```

必须记录的参数:

| 参数 | 作用 |
|---|---|
| `trajectory_tap_enabled` | 是否捕获扩散轨迹 |
| `tensor_types` | 捕获 latent / attention / feature 等张量类型 |
| `module_paths` | 捕获的模型模块路径 |
| `subspace_rank` | 子空间维度 |
| `sample_count` | 轨迹采样数量 |
| `timestep_stride` | 时间步采样间隔 |

### 3.5 几何同步、锚点、恢复与 rescue 检测

当前状态:

- CEG formal decision 已实现 geometry 诊断字段消费和 rescue 判定。
- 但真实几何锚点嵌入、攻击后对齐恢复、逆变换估计等数值实现仍是抽象保留。

论文结果包判定:

```text
必须补实际代码。
```

原因:

1. CEG 方法核心结论之一是 geometry rescue。
2. 仅有 `GeometryEvidence` 字段不足以证明攻击后恢复能力。
3. 攻击鲁棒性表和 TPR vs attack strength 曲线需要真实 geometry 恢复链支持。

应补内容:

```text
main/watermarking/geometry/
  anchor_embedder.py
  anchor_detector.py
  sync_template.py
  transform_estimator.py
  recovery.py
```

必须记录的参数:

| 参数 | 作用 |
|---|---|
| `registration_confidence_min` | 几何配准置信度门限 |
| `anchor_inlier_ratio_min` | 锚点内点比例门限 |
| `recovered_sync_consistency_min` | 恢复后一致性门限 |
| `align_max_iterations` | 对齐优化最大迭代次数 |
| `align_max_residual` | 允许的最大残差 |
| `anchor_count` | 几何锚点数量 |

### 3.6 Attestation 生成与检测

当前状态:

- CEG formal decision 已实现 `final_decision = evidence_decision and attestation_pass`。
- 但事件级 attestation 生成、密钥派生、提取与验证仍未作为 CEG 内部正式实现补齐。

论文结果包判定:

```text
必须补实际代码或明确降级论文主张。
```

原因:

1. Attestation 是 final-level 归因约束。
2. 如果只给一个外部 `attestation_score`, 无法证明归因链闭环。
3. 顶会审稿会要求说明密钥、事件绑定、伪造风险和检测统计。

应补内容:

```text
main/watermarking/attestation/
  key_derivation.py
  event_binding.py
  attestation_embedder.py
  attestation_detector.py
  attestation_score.py
```

必须记录的参数:

| 参数 | 作用 |
|---|---|
| `attestation_key_id` | 密钥或实验密钥标识 |
| `event_binding_mode` | event_id 与图像 / prompt 的绑定方式 |
| `attestation_threshold` | final-level attestation 门限 |
| `attestation_payload_bits` | 归因 payload 长度 |

### 3.7 真实 detection backend

当前状态:

- CEG 已有 fixed-FPR、表格重建和 detection output acceptance 的框架。
- 但正式 detector 仍未完整实现。

论文结果包判定:

```text
必须补实际代码。
```

原因:

1. TPR@FPR 必须来自真实 detector records。
2. detection 不能只由 dry-run producer 或手工 observation 文件替代。
3. baseline 和 attack 对比必须同口径进入 detector。

应补内容:

```text
scripts/run_ceg_real_detection_backend.py
main/watermarking/detect/
  detector_pipeline.py
  score_writer.py
  threshold_application.py
```

必须输出:

```text
records/detection_records.jsonl
records/calibration_records.jsonl
records/attack_detection_records.jsonl
manifests/detection_manifest.json
```

### 3.8 Attack 与质量指标

当前状态:

- CEG 已有 attack workflow、metric import、quality 表格结构等能力。
- 但正式论文需要真实 attacked 图像、真实 quality metrics 和验收报告。

论文结果包判定:

```text
必须补实际代码或正式外部命令接入。
```

原因:

1. 鲁棒性结论必须来自 attacked 图像和 attack detection records。
2. 质量结论必须来自真实图像质量指标。
3. 顶会论文不能只报告 clean detection。

必须覆盖的 attack family:

```text
jpeg_compression
gaussian_noise
gaussian_blur
crop
resize
rotation
color_jitter
diffusion_regeneration
```

必须覆盖的质量指标:

```text
psnr
ssim
lpips
```

建议补充:

```text
fid
clip_score
human_preference_summary
```

### 3.9 External baseline 真实接入

当前状态:

- CEG 已注册 Tree-Ring、Gaussian Shading、Shallow Diffuse、Stable Signature DEE 等 baseline 身份。
- 但注册身份不等于真实 baseline 结果。

论文结果包判定:

```text
必须补真实 baseline 运行输出或可复核外部结果导入。
```

原因:

1. 顶会论文必须与外部方法对比。
2. baseline 结果必须同口径进入 fixed-FPR 和质量统计。
3. 不能只保留 baseline 名称或空 adapter。

可接受方式:

1. 在 CEG 内调用 baseline 官方实现。
2. 使用外部 baseline 运行结果, 但必须有 observation 文件、manifest、命令记录和数据验收。
3. 对不可复现实验, 必须标注来源、版本、参数和限制, 且不得作为无来源 supported claim。

## 4. 非必要, 不应保留在 CEG 核心路径中的内容

### 4.1 CEG-WM 运行时依赖

判定:

```text
非必要, 且不应保留。
```

原因:

1. `D:\Code\CEG` 应成为独立论文项目。
2. Colab 正式流程不应 clone 或调用另一个项目。
3. 若需要 CEG-WM 的方法机制, 应迁移或重写为 CEG 内部模块。

处置:

- Notebook 不应拉取 `CEG-WM`。
- backend 不应调用 `CEG-WM` CLI。
- 文档可以引用 CEG-WM 作为历史来源或对齐对象, 但不能作为运行时依赖。

### 4.2 旧项目治理门禁与 workflow 状态

包括但不限于:

```text
freeze_gate
runtime_whitelist
policy_path_semantics
PWxx notebook 状态
旧项目阶段推进文件
Claude / Codex 钩子状态
```

判定:

```text
非必要, 不应进入核心方法路径。
```

原因:

1. 它们是旧项目工程治理, 不是论文方法。
2. 顶会结果包只需要可复核 provenance、records 和 manifests。
3. 过多旧门禁会污染 clean project 的可维护性。

处置:

- 可保留为历史审计文档。
- 不应被 `main/` 核心方法导入。
- 不应成为 Colab 正式运行前提。

### 4.3 第三方 baseline 源码整体复制

判定:

```text
通常非必要, 不建议保留在核心仓库。
```

原因:

1. 可能引入许可证、依赖和维护风险。
2. CEG 只需定义 baseline 接入协议、命令模板和结果验收。
3. baseline 官方实现可作为外部命令或子模块运行, 但必须记录版本与参数。

建议方式:

```text
experiments/baseline_command_adapter.py
configs/baseline_command_templates.json
baselines/<method>/baseline_manifest.json
```

### 4.4 与 formal decision 无关的旧标签别名

例如:

```text
final_reject
evidence_positive_by_content 字符串标签
high / medium / low 几何质量标签
```

判定:

```text
非必要, 可在导出层提供 alias, 不应污染核心判定逻辑。
```

原因:

1. CEG 当前已经输出布尔字段和 `final_label`。
2. 旧标签可由现有字段无损恢复。
3. 核心判定应保持简洁、可测试、可解释。

### 4.5 抽象保留但不支撑论文 claim 的字段

判定:

```text
非必要, 应从正式结果 claim 路径中移除或标记为 diagnostic-only。
```

原因:

1. 顶会论文不能用 placeholder 或抽象字段支撑结论。
2. 若字段没有真实生产者, 不应进入主表或主 claim。
3. 可保留在 docs 中作为未来实现计划, 但不能进入 supported claims。

## 5. CEG 当前差异更合理, 应保留的内容

### 5.1 records-first 产物治理

CEG 差异:

- CEG 强制论文表格、图和 reports 从 records 与 manifests 重建。

判定:

```text
CEG 更合理, 应保留。
```

原因:

1. 更符合顶会结果包复核要求。
2. 能避免手工拼表、手工挑图和无法追溯的 claims。
3. 便于审稿 rebuttal 与 artifact evaluation。

### 5.2 CEG 不调用 CEG-WM 运行时

CEG 差异:

- CEG 运行时自包含, 不依赖 CEG-WM。

判定:

```text
CEG 更合理, 必须保留。
```

原因:

1. 两个项目边界清晰。
2. CEG-WM 后续可移除。
3. 论文项目结果包更容易复现、归档和发布。

### 5.3 `rescue_delta_low` 使用非负窗口宽度

CEG 差异:

- CEG 使用 `rescue_delta_low` 作为非负窗口宽度, 使用时取负号。
- CEG-WM 文档表达中 `delta_low` 可写成负下界。

判定:

```text
CEG 更合理, 应保留。
```

原因:

1. 参数含义更直观。
2. 配置校验更简单, 可要求 `rescue_delta_low >= 0`。
3. 不改变 rescue 公式语义。

### 5.4 显式 None 检查

CEG 差异:

- `content_margin_aligned is not None` 等条件显式存在。

判定:

```text
CEG 更合理, 应保留。
```

原因:

1. 避免缺失字段误触发 rescue。
2. 有利于日志审计和异常路径解释。
3. 不改变方法公式, 只增强工程健壮性。

### 5.5 几何质量枚举使用 `reliable / borderline / unreliable / incomplete`

CEG 差异:

- CEG-WM 文档中可能使用 `high / medium / low`。
- CEG 当前使用更工程化的枚举。

判定:

```text
CEG 更合理, 可保留, 但导出层可提供论文别名。
```

原因:

1. `reliable` 直接对应 rescue eligibility。
2. `incomplete` 明确表示字段缺失, 比 `low` 更可审计。
3. 若论文图表需要更短标签, 可在导出层映射, 不改核心 records。

### 5.6 baseline 只注册身份与 adapter, 不复制算法本体

CEG 差异:

- CEG 当前注册 baseline 身份并提供外部接入边界。

判定:

```text
CEG 更合理, 应保留。
```

原因:

1. 避免第三方实现污染核心方法包。
2. 便于记录 baseline 来源、版本和命令。
3. 满足结果包 provenance 要求。

但必须补充:

```text
真实 baseline 结果文件或可复核外部运行命令。
```

### 5.7 Notebook 只做编排

CEG 差异:

- Notebook 不直接手写正式 records、tables、figures 或 manifests。

判定:

```text
CEG 更合理, 应保留。
```

原因:

1. Notebook 是 Colab 入口, 不是主方法实现。
2. 正式结果必须由仓库脚本生成。
3. 有利于离线复跑和审计。

## 6. “抽象保留”内容的最终处置表

| 内容 | 当前状态 | 论文结果包处置 | 理由 |
|---|---|---|---|
| 内容自适应路由 | 抽象保留 | 必须补实际代码或删除方法主张 | 支撑 semantic-aware watermark |
| InSPyReNet / semantic mask | 抽象保留 | 必须补实际代码或删除相关消融 | 支撑 mask 贡献结论 |
| LF 内容链 | 抽象保留 | 必须补实际代码 | 支撑主检测分数 |
| HF 内容链 | 抽象保留 | 必须补实际代码或降级方法 | 支撑 harder regime 结论 |
| 子空间规划 / JVP | 抽象保留 | 若声称 latent method, 必须补代码 | 支撑扩散模型方法贡献 |
| 几何锚点嵌入 | 抽象保留 | 必须补实际代码 | 支撑 geometry rescue |
| 几何恢复检测 | 抽象保留 | 必须补实际代码 | 支撑 attack robustness |
| Attestation 生成与验证 | 抽象保留 | 必须补实际代码或降级 final claim | 支撑归因约束 |
| Payload probe | 抽象保留 | 可选, diagnostic-only | 不进入 formal decision |
| bit accuracy | 未实现 | 如果声明 bit recovery, 必须补 | 支撑 payload recovery 表 |
| 质量指标 | 未完整实现 | 必须补 | 支撑视觉质量结论 |
| external baseline 结果 | 身份注册 | 必须补结果或外部命令 | 支撑 baseline 对比 |
| 旧 workflow 门禁 | 不属于核心方法 | 不需要保留在核心路径 | 不支撑论文方法 |
| 旧标签别名 | 表示差异 | 可选导出 alias | 不影响核心判定 |

## 7. 面向实现的优先顺序

### 7.1 立即必须实现

这些内容决定是否能产出正式主结果:

1. CEG 内部正式 watermark embedding pipeline。
2. CEG 内部正式 detector pipeline。
3. calibration / test fixed-FPR 统计闭环。
4. attack 后 detection records。
5. baseline 真实结果接入。
6. PSNR / SSIM / LPIPS 质量指标。

### 7.2 论文方法主张相关, 必须二选一

这些内容必须在“实现”和“删除主张”之间做选择:

| 内容 | 选择 A | 选择 B |
|---|---|---|
| InSPyReNet / semantic mask | 实现并进入 Full 方法 | 从方法图、消融和结论中删除 |
| LF / HF 双分支 | 实现双分支和对应消融 | 将论文方法降级为单分支 |
| geometry rescue | 实现真实锚点与恢复 | 删除 rescue 贡献结论 |
| attestation | 实现事件级归因闭环 | 将 final-level claim 降级为 detection-only |
| bit recovery | 实现 bit extraction 和 bit accuracy | 不报告 bit recovery |

### 7.3 可以后置实现

这些内容对顶会加分, 但不是最小主结果闭环的第一阻断项:

1. FID。
2. CLIP score。
3. human preference。
4. 更丰富的攻击家族。
5. 多模型跨模型泛化。
6. 运行成本 profiling 的细粒度分解。

## 8. 结论

按照“顶会论文结果包”原则, `ceg_wm_method_alignment_audit.md` 中很多“抽象保留”不能继续停留在抽象层。如果这些机制支撑论文主方法、主表、主图或核心结论, 就必须在 `D:\Code\CEG` 内部补成实际代码、实际参数和实际 records。

当前可以明确保留的 CEG 差异包括:

1. records-first 产物治理。
2. 不调用 CEG-WM 运行时。
3. Notebook 只做编排。
4. 非负 rescue 窗口参数。
5. 显式缺失值检查。
6. 更可审计的几何质量枚举。
7. baseline adapter 边界而非复制第三方源码。

当前应避免继续保留在核心路径中的内容包括:

1. CEG-WM 运行时依赖。
2. 旧 workflow / 旧门禁。
3. 无真实生产者的正式 claim 字段。
4. 仅用于兼容旧日志的标签别名。
5. 不支撑论文结果包的抽象占位机制。

最终判断:

```text
CEG 当前 formal decision 层与 CEG-WM 方法机制保持一致, 但距离顶会论文结果包仍缺少正式水印、正式检测、真实攻击、真实 baseline、真实质量指标和可复核统计闭环。
```
