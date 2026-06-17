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
