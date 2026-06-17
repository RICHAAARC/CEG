# CEG 项目推进补充记录: 内部水印运行时模块化

## 1. 本次推进目标

本次推进仅参考 CEG-WM 的方法边界, 不调用 CEG-WM 运行时, 也不修改 CEG-WM 项目。目标是在 `D:\Code\CEG` 内部建立水印运行时模块的落点, 使后续正式 CEG 水印机制可以逐步迁移或重写到 CEG 项目中。

## 2. 本次新增内容

新增 CEG 内部水印包:

```text
main/watermarking/
  __init__.py
  native_lsb.py
```

同时将 `scripts/run_pilot_real_image_generation_backend.py` 中原本内联的 `ceg_native_lsb` 水印逻辑改为调用:

```python
from main.watermarking.native_lsb import embed_native_lsb_watermark
```

## 3. 当前 `ceg_native_lsb` 的定位

`ceg_native_lsb` 的定位是:

```text
pilot_self_contained_pixel_watermark
```

它的作用是:

1. 保证 Colab 图像生成链路不依赖 CEG-WM。
2. 真实改写 clean 图像像素, 生成 watermarked 图像。
3. 提供可复现 bit 序列和 manifest reporting surface。
4. 为后续正式 CEG embedding pipeline 提供可替换接口。

它不是:

```text
paper_main_method_ready
```

也不能替代正式论文方法中的 semantic mask、LF / HF、geometry rescue 和 attestation。

## 4. 为什么要先做模块化

此前 pilot 水印逻辑内联在脚本中, 存在三个问题:

1. 脚本职责过重, 不利于后续替换为正式 CEG 水印方法。
2. Notebook 调度入口与方法原语边界不够清晰。
3. 后续 detector 无法稳定复用相同 bit 生成规则。

模块化后, 项目边界变为:

```text
scripts/run_pilot_real_image_generation_backend.py
  负责 Colab / CLI 编排、SD 调用、文件写出、验收

main/watermarking/native_lsb.py
  负责 CEG 内部 pilot 水印原语

未来 main/watermarking/<formal_modules>.py
  负责正式 CEG 方法原语
```

## 5. 与 CEG-WM 的关系

本次推进遵循以下原则:

1. 只参考 CEG-WM 的方法机制和差距审计。
2. 不 clone、不 import、不 subprocess 调用 CEG-WM。
3. 需要的机制后续必须在 CEG 内部重写或迁移。
4. CEG-WM 可以作为历史对照文档, 不能作为正式运行依赖。

## 6. 当前仍未完成的正式论文方法能力

以下能力仍未完成, 不能因为 `ceg_native_lsb` 已模块化而视为论文主方法已具备:

1. InSPyReNet / semantic mask backend。
2. LF 内容链嵌入与检测。
3. HF 内容链嵌入与检测。
4. 子空间规划、JVP 和扩散轨迹采样。
5. 几何同步、锚点、恢复与 rescue 检测。
6. Attestation 生成、绑定与检测。
7. 真实 CEG detector。
8. bit recovery 与 bit accuracy。
9. 与 baseline 同口径的正式 records。

## 7. 下一步建议

建议按以下顺序继续推进:

1. 新增 `main/watermarking/interfaces.py`, 定义正式 embedding / detection 接口。
2. 新增 `main/watermarking/semantic_mask.py`, 先定义 mask contract, 再接入 InSPyReNet 或等价 backend。
3. 新增 `main/watermarking/content_chain/`, 实现 LF / HF score 生产路径。
4. 新增 `main/watermarking/geometry/`, 实现 anchor、sync 和 recovery。
5. 新增 `main/watermarking/attestation/`, 实现 event binding 和 attestation score。
6. 新增 `scripts/run_ceg_real_detection_backend.py`, 产出真实 detection records。
7. 将 `ceg_native_lsb` 明确保留为 pilot / smoke backend, 不进入论文主结果 claim。

## 8. 验收判据

本次推进完成后, 应满足:

1. `scripts/run_pilot_real_image_generation_backend.py` 不再内联 pilot 水印算法主体。
2. CEG 内部水印模块可被单元或轻量功能测试直接调用。
3. 水印报告显式标记 `paper_main_method_ready = false`。
4. CEG-WM 工作区没有任何改动。
5. pytest、harness audit 和 completion audit 通过。

## 9. 本次继续推进: 水印运行时接口层

在移除旧分支提交引用后, 本次继续在 CEG 项目内部补充了:

```text
main/watermarking/interfaces.py
```

该文件定义以下通用方法契约:

1. `WatermarkPromptContext`: 统一保存 `image_id`、`prompt_id`、prompt 文本、seed、模型标识和生成参数。
2. `WatermarkEmbeddingRequest`: 统一描述 clean 图像输入、watermarked 图像输出和水印配置。
3. `WatermarkEmbeddingResult`: 统一描述嵌入结果、backend 身份、backend 职责、正式论文可用性和 provenance。
4. `WatermarkDetectionRequest`: 统一描述检测输入图像、prompt 上下文和 detector 配置。
5. `WatermarkDetectionResult`: 统一描述检测分数、阈值、判定和检测 provenance。
6. `WatermarkEmbedder` / `WatermarkDetector`: 定义后续 backend 可替换协议。

该接口层属于通用工程写法, 其价值在于把不同水印 backend 的输入输出边界固定下来。
但 `paper_main_method_ready` 属于 CEG 项目特定字段, 用于防止 pilot backend 被误纳入正式论文主方法结论。

## 10. 本次没有迁入的 CEG-WM 内容

本次只参考 CEG-WM 的方法边界, 没有迁入以下内容:

1. CEG-WM 的复杂门禁规则。
2. CEG-WM 的 workflow 框架。
3. CEG-WM 的 GitNexus 或 harness 约束。
4. CEG-WM 的项目目录结构。
5. 对 CEG-WM 仓库的 import、clone 或 subprocess 调用。

这些内容不属于 CEG 主方法实现, 如果放入 `main/` 会污染方法原语边界。

## 11. 接口层之后的推进顺序

后续应在上述接口契约下继续补充真实方法实现:

1. `semantic_mask.py`: 接入 InSPyReNet 或等价 segmentation backend, 产出 semantic mask records。
2. `content_chain/`: 实现 LF/HF 内容链嵌入与检测分数。
3. `geometry/`: 实现 anchor、sync、registration 和 recovery。
4. `attestation/`: 实现图像、prompt、方法配置和检测事件的绑定证明。
5. `scripts/run_ceg_real_detection_backend.py`: 读取 `image_pairs.json`, 运行真实 detector, 写出可统计 TPP@FPR 的 detection records。

这些实现应复用 `interfaces.py` 的请求和结果结构, 而不是把 notebook、Google Drive 打包或 harness 门禁逻辑写入方法模块。

## 12. 本次继续推进: 真实图像驱动 semantic mask 原语

在接口层之后, 本次继续补充了 CEG 内部真实方法原语:

```text
main/watermarking/semantic_mask.py
```

该模块的职责是把输入图像转换为可复现的二值 mask、mask 统计量、空间绑定和 digest。
它不包含 Colab 调度、Google Drive 打包、harness 门禁或 CEG-WM 兼容逻辑。

### 12.1 已实现能力

1. `gradient_saliency` backend:
   - 读取真实图像像素。
   - 计算灰度梯度能量。
   - 按分位数阈值生成高显著性区域 mask。
   - 执行可配置开闭运算。
   - 生成 `mask_digest` 与 `routing_digest`。
   - 生成 `area_ratio`、`connected_components`、`largest_component_ratio`、`boundary_length`、`downsample_grid_digest` 等统计量。
   - 可写出二值 mask 图像。

2. `inspyrenet` backend:
   - 提供真实 InSPyReNet 入口。
   - 当运行环境安装 `transparent_background` 且具备权重时, 调用 `Remover.process(..., type="map")` 生成 saliency map。
   - 当依赖不可用时显式失败, 不自动降级为 proxy, 防止正式实验误用。

### 12.2 当前定位

该模块是 CEG 论文方法中的一个原语, 对应 semantic mask / LF-HF routing 的输入侧能力。
它仍然不是完整论文主方法, 因为尚未同时实现:

1. LF / HF 内容链嵌入。
2. LF / HF 内容链检测。
3. 几何同步与 recovery。
4. Attestation 绑定。
5. 同口径 TPP@FPR detection records。

因此模块输出继续保留:

```text
paper_main_method_ready = false
```

### 12.3 与 CEG-WM 的关系

本次仅参考 CEG-WM 中 semantic mask provider 的方法思想:

1. mask 应绑定图像分辨率。
2. mask 应有 digest。
3. mask 应有面积、连通域和低分辨率网格统计。
4. saliency source 应显式记录。
5. model backend 不可用时不应静默伪装为正式模型结果。

没有迁入 CEG-WM 的复杂门禁、workflow、历史 archive 测试或项目运行时依赖。

### 12.4 下一步

下一步应在 `main/watermarking/content_chain/` 下补充 LF/HF 内容链, 使 semantic mask 的 `mask_true -> hf` 与 `mask_false -> lf` 路由真正进入 embedding 和 detection 分数生产路径。

## 13. 本次继续推进: LF/HF 内容链证据原语

在 semantic mask 原语之后, 本次继续补充了 CEG 内部内容链原语:

```text
main/watermarking/content_chain/
  __init__.py
  scoring.py
```

该模块把 semantic mask 的空间路由转换为可复现的 LF/HF 内容链证据:

1. `mask_false -> lf`:
   - 从低显著性区域提取低频亮度块均值向量。
   - 绑定 prompt、mask digest、routing digest 和配置派生 LF challenge。
   - 计算 `lf_score`、`lf_trace_digest` 和 `lf_statistics_digest`。

2. `mask_true -> hf`:
   - 从高显著性区域提取梯度能量块向量。
   - 绑定 prompt、mask digest、routing digest 和配置派生 HF challenge。
   - 计算 `hf_score`、`hf_trace_digest` 和 `hf_statistics_digest`。

3. 汇总路径:
   - 按权重合成 `content_score`。
   - 写出 `content_chain_digest`。
   - 输出可进入 detection record 的 `score_parts` 和 `diagnostics`。

### 13.1 当前实现的真实性边界

该模块读取真实图像像素和真实 semantic mask, 因此不是 mock 或空实现。
但它仍然只是内容链 evidence 生产路径, 不是完整论文主方法, 因为尚未实现:

1. 内容链 embedding 侧图像改写。
2. 几何攻击后的同步恢复。
3. Attestation 绑定。
4. 与真实 positive / negative 样本集合联动的固定 FPR 阈值校准。

因此模块输出继续保留:

```text
paper_main_method_ready = false
```

### 13.2 与 CEG-WM 的关系

本次仅参考 CEG-WM 的 LF/HF 内容链机制思想:

1. 内容 evidence 应拆分 LF 与 HF 分支。
2. 每个分支应有独立 trace digest。
3. 分支分数应可合成为总 content score。
4. 分支统计应绑定 mask digest 和 prompt 上下文。

没有迁入 CEG-WM 的 LDPC 门禁、paper faithfulness gate、runtime resolver、workflow 或历史复杂约束。

### 13.3 下一步

下一步应补充内容链 embedding 原语, 使当前检测侧 LF/HF score 能够对应到真实 watermarked 图像中的可控改写。建议新增:

```text
main/watermarking/content_chain/embedding.py
```

该模块应基于 semantic mask 分区, 对 LF 区域和 HF 区域施加可控、可复现且有 provenance 的像素或频域扰动。

## 14. 本次继续推进: 内容链 embedding 图像改写原语

在 LF/HF 内容链 scoring 原语之后, 本次继续补充了 embedding 侧图像改写能力:

```text
main/watermarking/content_chain/embedding.py
```

该模块让 `semantic mask -> LF/HF routing -> content score` 不再只是检测侧 evidence, 而是具备对应的真实图像改写来源。

### 14.1 已实现能力

1. `mask_false -> lf`:
   - 在低显著性区域按固定网格施加平滑亮度偏移。
   - 网格 challenge 由 prompt、mask digest、routing digest 和配置稳定派生。
   - 输出 `lf_embedding_trace_digest`。

2. `mask_true -> hf`:
   - 在高显著性区域施加细粒度符号扰动。
   - 扰动模式由 prompt、mask digest、routing digest 和配置稳定派生。
   - 使用互补 RGB 通道符号降低整体亮度漂移。
   - 输出 `hf_embedding_trace_digest`。

3. manifest provenance:
   - 写出真实 watermarked 图像。
   - 输出 `embedding_digest`、`changed_pixel_count`、`changed_channel_count`、LF/HF 修改像素数和 diagnostics。

### 14.2 当前真实性边界

该模块执行真实像素改写, 不是 mock、复制图像或空产物。
但它仍然不是完整论文主方法, 因为尚未实现:

1. 攻击后的几何同步和 recovery。
2. Attestation 事件绑定。
3. 图像生成 backend 中对该 embedding 原语的正式接入。
4. detection producer 中对该 content chain score 的正式接入。
5. 固定 FPR 阈值校准和 TPP@FPR 统计闭环。

因此模块输出仍然保留:

```text
paper_main_method_ready = false
```

### 14.3 与 CEG-WM 的关系

本次只参考 CEG-WM 的 LF/HF 双通道思想和 trace digest 思路。
没有迁入 CEG-WM 的 LDPC 约束、paper faithfulness gate、runtime resolver、复杂流程框架或门禁逻辑。

### 14.4 下一步

下一步应把该 embedding 原语接入真实图像生成 backend:

```text
scripts/run_pilot_real_image_generation_backend.py
```

建议保留 `ceg_native_lsb` 作为 pilot fallback, 新增可选 backend:

```text
ceg_content_chain_embedding
```

该 backend 应写出 `image_pairs.json`、`image_generation_manifest.json` 和 `image_pair_manifest.json` 中可追溯的 embedding provenance。

## 15. 本次继续推进: 真实图像生成 backend 接入内容链 embedding

在内容链 embedding 原语完成后, 本次继续将其接入真实图像生成入口:

```text
scripts/run_pilot_real_image_generation_backend.py
```

新增可选水印 backend:

```text
ceg_content_chain_embedding
```

同时保留原有 fallback:

```text
ceg_native_lsb
```

### 15.1 新 backend 行为

当 CLI 使用:

```bash
--watermark-backend ceg_content_chain_embedding
```

脚本会对每张 clean 图像执行:

1. 从 clean 图像提取 semantic mask。
2. 将 mask 写入 `semantic_masks/`。
3. 调用 `embed_content_chain_watermark` 执行真实 LF/HF 内容链像素改写。
4. 写出 watermarked 图像。
5. 在 backend manifest 的 `watermark_runs` 中记录:
   - `semantic_mask_digest`
   - `semantic_routing_digest`
   - `embedding_digest`
   - `lf_embedding_trace_digest`
   - `hf_embedding_trace_digest`
   - `changed_pixel_count`
   - `changed_channel_count`
   - LF/HF 修改像素数

### 15.2 新增 CLI 参数

新增参数包括:

```text
--content-mask-threshold-quantile
--content-mask-open-iters
--content-mask-close-iters
--content-lf-grid-size
--content-lf-strength
--content-hf-strength
```

这些参数只控制 CEG 内容链方法原语, 不引入 CEG-WM 的 workflow 或门禁。

### 15.3 当前边界

当前 Colab / CLI 图像生成链路已经可以直接产出内容链 watermarked 图像。
但该 backend 仍显式标记:

```text
paper_main_method_ready = false
```

原因是还缺:

1. 攻击后几何同步与 recovery。
2. Attestation 事件绑定。
3. detection producer 对内容链 score 的正式接入。
4. 固定 FPR 阈值校准与 TPP@FPR 统计闭环。

### 15.4 下一步

下一步应补充真实 detection backend, 读取 `image_pairs.json` 和 `watermark_runs` provenance, 对 clean / watermarked / attacked 图像运行 semantic mask 与内容链 scoring, 输出可进入固定 FPR 统计的 detection records。


## 16. 本次继续推进: 真实内容链 detection backend

在图像生成 backend 已经能够产出内容链 watermarked 图像之后, 本次继续补充了真实检测入口:

```text
experiments/ceg_real_detection_backend.py
scripts/run_ceg_detection_producer.py --detection-backend ceg_content_chain_detection
```

### 16.1 已实现能力

该 backend 会读取 `image_pairs.json`, 并对每一组样本生成两类检测事件:

1. `clean_negative`: 对 clean 图像运行检测, 用于后续固定 FPR 阈值校准。
2. `positive_source`: 对 watermarked 图像运行检测, 用于后续 TPP / TPR 统计。

如果提供 `attacked_image_manifest.json`, backend 还会对 attacked 图像生成 `attacked_positive` 或
`attacked_negative` 事件。每个事件都会真实执行:

1. `extract_semantic_mask`: 读取图像像素并生成 semantic mask、mask digest 和 routing digest。
2. `extract_content_chain_evidence`: 在 mask 路由下提取 LF / HF 内容链分数。
3. 写出统一协议事件 `detection_events.json`。
4. 写出 `content_chain_detection_records.json`, 便于后续审计每张图像的 mask 与 content chain provenance。
5. 写出 `ceg_detection_producer_manifest.json`, 记录 producer、配置、事件数量和 digest。

### 16.2 与旧 dry-run producer 的关系

旧的 `contract_dry_run` 路径仍然保留, 用于快速验证事件协议、表格重建和结果包链路。新的
`ceg_content_chain_detection` 路径不是 dry-run 分数, 它会读取真实图像并计算真实内容链分数。

两者的 CLI 入口统一在:

```bash
python scripts/run_ceg_detection_producer.py \
  --image-pairs <image_pairs.json> \
  --out <detection_dir> \
  --detection-backend ceg_content_chain_detection
```

### 16.3 当前边界

该 backend 仍显式标记:

```text
formal_result_claim = false
paper_main_method_ready = false
```

原因是当前只完成了 semantic mask 与内容链 scoring 闭环, 仍缺少:

1. 攻击后的几何同步、registration 和 recovery。
2. 事件级 attestation 绑定与验证。
3. 基于完整校准集的固定 FPR 阈值选择。
4. 与外部 baseline 在同一正式数据规模下的最终对比运行。

因此该 backend 的主要价值是把真实图像水印产物接入 TPP@FPR 所需的 records 形态, 不是直接声明最终论文主结果。

### 16.4 下一步

下一步应继续补充 `main/watermarking/geometry/` 和 `main/watermarking/attestation/`。只有当 detection 事件同时包含:

1. 内容链原始分数与恢复后分数。
2. 几何恢复质量指标。
3. attestation score。
4. clean negative 校准集合。
5. attacked positive 评测集合。

项目才能稳定产出论文主表中的固定 FPR 下 TPP / TPR 结果。


## 17. 本次继续推进: 几何 registration 与恢复评分接入

在真实内容链 detection backend 之后, 本次继续补充了几何恢复方法原语:

```text
main/watermarking/geometry/
  __init__.py
  registration.py
```

### 17.1 已实现能力

当前几何原语提供 `estimate_geometry_registration` 入口, 对 target 图像和 reference 图像执行真实像素级平移搜索:

1. 读取 target / reference 图像像素。
2. 转换为归一化灰度图。
3. 在整数平移窗口内搜索最大归一化互相关。
4. 计算 `registration_confidence`、`anchor_inlier_ratio`、`recovered_sync_consistency` 和 `alignment_residual`。
5. 写出 aligned 图像, 供内容链 detector 重新计算恢复后分数。
6. 生成 `alignment_digest`、reference digest 和 target digest, 便于记录审计。

该能力已经接入:

```text
experiments/ceg_real_detection_backend.py
```

每个 detection event 现在包含:

1. `payload.content.content_score_raw`: 原始 target 图像内容链分数。
2. `payload.content.content_score_aligned`: 几何对齐图像内容链分数。
3. `payload.geometry.geometry_record`: 几何 registration provenance。
4. `payload.aligned_content_chain`: 对齐后内容链 provenance。
5. `aligned_images/`: 对齐图像落盘目录。

### 17.2 当前边界

该几何模块属于真实方法原语, 但还不是完整顶会论文级几何恢复 backend。当前实现主要覆盖平移和轻量裁剪类偏移诊断, 尚未覆盖:

1. 旋转恢复。
2. 尺度恢复。
3. 透视变换恢复。
4. 局部非刚性形变恢复。
5. 多锚点特征匹配和鲁棒估计。

因此 detection backend 的 blocking reason 已从“完全没有几何恢复”推进为:

```text
full_affine_or_feature_geometry_recovery_not_implemented
```

这表示项目已经具备真实几何恢复原语, 但仍需增强到完整 affine / feature-based recovery 才能支撑正式论文主结果。

### 17.3 下一步

下一步建议继续补充 attestation 绑定模块:

```text
main/watermarking/attestation/
```

该模块应把图像、prompt、mask digest、content chain digest、geometry digest 和方法配置绑定为事件级证明, 并输出 `attestation_score`。只有 attestation 接入后, CEG formal decision 中的 `final_decision = evidence_decision AND attestation_pass` 才能从真实 backend 获得完整输入。


## 18. 本次继续推进: 事件级 attestation 绑定原语

在几何 registration 接入之后, 本次继续补充了事件级 attestation 方法原语:

```text
main/watermarking/attestation/
  __init__.py
  binding.py
```

### 18.1 已实现能力

当前 attestation backend 为公开 digest 级 evidence binding, 入口为:

```text
build_attestation_binding
```

该入口会把以下信息绑定为一个可审计 record:

1. `event_id`、`method_name` 和 `sample_role`。
2. `WatermarkPromptContext` 中的 image / prompt / seed / model 绑定。
3. semantic mask 的 `mask_digest` 和 `routing_digest`。
4. 原始内容链和几何对齐后内容链的 `content_chain_digest`。
5. 几何 registration 的 `alignment_digest` 和质量指标。
6. 图像 provenance 中的 image / reference / aligned 路径。

输出字段包括:

```text
attestation_score
attestation_digest
evidence_bundle_digest
verifier_digest
check_results
```

### 18.2 detection backend 接入

`experiments/ceg_real_detection_backend.py` 现在不再固定写入 `attestation_score = 0.0`, 而是在每个 event 中调用
`build_attestation_binding`。因此 CEG formal decision 的输入已经同时具备:

1. 内容链原始分数。
2. 几何恢复后分数。
3. 几何质量指标。
4. attestation score。

这使 `final_decision = evidence_decision AND attestation_pass` 可以消费真实 backend 产生的 attestation 字段。

### 18.3 当前边界

该实现是真实的一致性检查和 digest 绑定, 不是 mock, 但仍不是最终论文级 attestation。原因是它尚未包含:

1. keyed signature。
2. 外部可信 verifier。
3. 与模型生成过程绑定的不可抵赖证明。
4. 跨机器或跨运行环境的密钥管理。

因此 backend 继续保持:

```text
paper_main_method_ready = false
```

blocking reason 已推进为:

```text
public_digest_attestation_lacks_keyed_or_external_verifier
```

### 18.4 下一步

下一步应继续推进固定 FPR 校准和真实结果包闭环, 使 clean negative 集合能够校准阈值, positive / attacked 集合能够产出论文表格中的 TPP@FPR / TPR@FPR 指标。


## 19. 本次继续推进: detection events 的 fixed FPR 阈值校准回写

在真实 detection backend 已经具备 content、geometry 和 attestation 字段之后, 本次继续补齐 fixed FPR 校准与
formal decision 的关键衔接:

```text
experiments/detection_event_thresholds.py
scripts/calibrate_detection_events_fixed_fpr.py
```

### 19.1 为什么需要回写 detection events

CEG 的 formal decision 读取的是每个事件中的:

```text
payload.thresholds.content_threshold
```

而不仅仅是外部传入的 thresholds JSON。外部 thresholds JSON 主要用于 artifact 审计和表格重建。若 fixed FPR
校准只生成旁路 thresholds 文件, 但不更新 detection event, 则后续 `run_paper_protocol` 仍会按旧阈值执行
`decide_ceg_event`。因此真实 fixed FPR 闭环必须生成一份:

```text
detection_events_calibrated.json
```

### 19.2 已实现能力

新模块会执行以下步骤:

1. 读取 `detection_events.json`。
2. 优先使用 `split = calibration` 且 `sample_role = clean_negative` 的事件收集 negative scores。
3. 若正式 calibration split 不存在, 显式退回到 `fallback_all_clean_negative`, 便于 pilot 阶段继续运行。
4. 根据目标 FPR 计算内容阈值。
5. 把阈值回写到每个事件的 `payload.thresholds.content_threshold`。
6. 在 `payload.detection_source` 中记录 `fixed_fpr_calibrated = true` 和阈值来源。
7. 写出:
   - `detection_events_calibrated.json`
   - `detection_thresholds_calibrated.json`
   - `detection_event_threshold_calibration_report.json`

### 19.3 运行入口

```bash
python scripts/calibrate_detection_events_fixed_fpr.py \
  --events <detection_events.json> \
  --out <calibrated_detection_dir> \
  --target-fpr 0.01
```

后续构建论文结果包时, 应把 `detection_events_calibrated.json` 作为 `build_paper_outputs.py --events` 的输入,
把 `detection_thresholds_calibrated.json` 作为 `--thresholds` 的输入。

### 19.4 当前边界

该能力已经把 fixed FPR 阈值校准接入真实 detection event, 但 pilot 数据规模仍可能不足以支撑正式论文声明。
正式论文结果仍需要:

1. 足够数量的 calibration clean negative 样本。
2. 独立 test split。
3. attacked positive 评测集合。
4. 外部 baseline 的同口径 calibrated events 或 observations。

因此该步骤是从真实 backend 到论文 TPP@FPR 表格的必要桥梁, 但不是最终数据规模本身。


## 20. 本次继续推进: fixed-FPR 校准后论文结果包一键构建入口

在 detection events fixed-FPR 阈值回写能力之后, 本次继续新增了一个流水线入口:

```text
scripts/build_calibrated_paper_results_package.py
```

### 20.1 解决的问题

在当前真实方法链路中, 从 detection backend 到论文结果包至少需要三个步骤:

1. 对 `detection_events.json` 执行 fixed-FPR 阈值校准, 生成 `detection_events_calibrated.json`。
2. 使用已校准事件运行 `build_paper_outputs.py`, 生成论文表格、图表、报告和 readiness 报告。
3. 使用 `export_paper_results_package.py` 导出可交付结果包。

如果这些步骤由人工手工拼接, 最容易出现的错误是: 校准了 thresholds, 但后续仍把未校准的
`detection_events.json` 传给 paper protocol。这样 formal decision 会继续使用旧的
`payload.thresholds.content_threshold`, 导致 fixed-FPR 统计与 formal decision 不一致。

### 20.2 新入口行为

新脚本会顺序执行:

```text
calibrate_detection_events_fixed_fpr.py
build_paper_outputs.py
export_paper_results_package.py
```

并固定把以下文件传给后续步骤:

```text
calibrated_detection/detection_events_calibrated.json
calibrated_detection/detection_thresholds_calibrated.json
calibrated_detection/detection_event_threshold_calibration_report.json
```

其中 calibration report 会作为 detection execution manifest 复制进入结果包 provenance。

### 20.3 运行方式

```bash
python scripts/build_calibrated_paper_results_package.py \
  --detection-events <detection_events.json> \
  --out <package_run_dir> \
  --target-fpr 0.01 \
  --image-pairs <image_pairs.json> \
  --attacked-image-manifest <attacked_image_manifest.json> \
  --attack-shard-manifest <attack_shard_manifest.json>
```

可选参数可以继续传入 baseline、metric rows、experiment matrix 和 readiness requirements。

### 20.4 输出目录

```text
<package_run_dir>/
  calibrated_detection/
  paper_outputs/
  paper_results_package/
  calibrated_paper_results_package_build_manifest.json
```

这使 Colab 或本地正式运行可以把结果直接保存到 Google Drive 的 CEG 目录下, 并且保留完整执行摘要。

### 20.5 当前边界

该脚本完成的是流程闭环, 不是替代真实实验规模。正式论文结果仍需要:

1. 足够规模的 calibration clean negative。
2. 独立 test split。
3. attacked positive 测试集合。
4. 外部 baseline 同口径输入。
5. 更强 geometry 和 keyed / external attestation。

但从工程闭环角度, 当前已经可以从真实 detection events 一条命令进入 fixed-FPR 校准后的论文结果包构建。
