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
