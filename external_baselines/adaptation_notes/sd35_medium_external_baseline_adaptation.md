# External Baseline SD3.5 Medium Adaptation Notes

## 1. 共同输入输出契约

外部 baseline 后续都应适配为相同的命令形态。不同方法可以读取不同前置输入:
Tree-Ring 这类扩散生成水印 baseline 读取 `prompt_plan.json`, T2SMark 这类外部已运行方法可以读取
其自身 `results.json` 与 CEG `image_pairs.json`。

```bash
python external_baselines/<group>/<baseline>/adapter/run_ceg_eval.py \
  --prompt-plan <prompt_plan.json> \
  --out <baseline_observations.json> \
  --model-id stabilityai/stable-diffusion-3.5-medium
```

输出必须是 CEG 已支持的 observation rows:

```json
{
  "event_id": "...",
  "baseline_id": "tree_ring",
  "score": 0.0,
  "threshold": 0.5,
  "split": "test",
  "sample_role": "attacked_positive",
  "attack_family": "jpeg"
}
```

该结构属于项目特定写法, 用于让 `scripts/run_baseline_plan.py` 和 `scripts/run_colab_paper_results_pipeline.py` 不关心第三方仓库内部实现。

## 2. 主表 baseline 适配判断

### 2.1 Tree-Ring

- 原仓库入口候选: `run_tree_ring_watermark.py`, `inverse_stable_diffusion.py`, `modified_stable_diffusion.py`。
- 当前状态: 已补充 CEG adapter, 路径为
  `external_baselines/main_table/tree_ring_watermark/adapter/run_ceg_eval.py`。
- 已适配内容:
  - 读取 CEG `prompt_plan.json`, 直接调用 `stabilityai/stable-diffusion-3.5-medium` 生成 clean 与 Tree-Ring watermarked 图像。
  - 将原始 SD2 常见 latent shape `(1, 4, 64, 64)` 显式扩展为 SD3.5 Medium 的
    `(1, 16, height / 8, width / 8)`。
  - 保留 Tree-Ring 的傅里叶域复数 key, 并按原始 `w_radius` 生成 ring/rand/zeros key。
  - 通过 SD3 VAE 编码和轻量 forward diffusion 近似恢复检测 latent, 输出 CEG 统一
    `baseline_observations.json`。
  - 可选运行 CEG 轻量攻击 workflow, 产生 attacked-positive 与 attacked-negative observation。
- 已接入 plan builder:
  `scripts/build_tree_ring_adapter_baseline_plan.py`。
- 仍需正式 GPU 运行验证: 该适配器已经是可执行链路, 但 Tree-Ring 在 SD3.5 Medium 上的论文数值必须
  通过 Colab / GPU 正式运行产物确认, 不能用本地静态校验替代。

### 2.2 Gaussian Shading

- 原仓库入口候选: `run_gaussian_shading.py`, `watermark.py`, `inverse_stable_diffusion.py`。
- 当前状态: 已补充 CEG adapter, 路径为
  `external_baselines/main_table/gaussian_shading/adapter/run_ceg_eval.py`。
- 已适配内容:
  - 读取 CEG `prompt_plan.json`, 直接调用 `stabilityai/stable-diffusion-3.5-medium`。
  - 将原始 `4 x 64 x 64` latent 显式推广为 SD3.5 Medium 的 `16 x H/8 x W/8`。
  - 保留 Gaussian Shading 的核心原语: bit message、key 异或、截断高斯采样、反演后符号解码、
    `channel_copy` / `hw_copy` 重复投票和 bit accuracy 分数。
  - 输出 CEG 统一 `baseline_observations.json`, 并可选生成 attacked-positive 与 attacked-negative observation。
- 已接入统一 plan builder:
  `scripts/build_sd35_external_adapter_baseline_plan.py`。
- 仍需正式 GPU 运行验证: 当前本地只能完成静态校验和命令计划生成。

### 2.3 Shallow Diffuse

- 原仓库入口候选: `run_shallow_diffuse_t2i.py`, `run_shallow_diffuse_i2i.py`, `inverse_stable_diffusion.py`。
- 当前状态: 已补充 CEG adapter, 路径为
  `external_baselines/main_table/shallow_diffuse/adapter/run_ceg_eval.py`。
- 已适配内容:
  - 读取 CEG `prompt_plan.json`, 直接调用 `stabilityai/stable-diffusion-3.5-medium`。
  - 使用 SD3.5 latent shape, 并保留 Shallow Diffuse 的核心原语:
    浅层/局部 latent 子空间 mask、patch 注入、非水印区域保留、反演后 patch 距离检测。
  - 输出 CEG 统一 `baseline_observations.json`, 并可选生成 attacked-positive 与 attacked-negative observation。
- 已接入统一 plan builder:
  `scripts/build_sd35_external_adapter_baseline_plan.py`。
- 仍需正式 GPU 运行验证: 当前适配器是可执行链路, 但论文数值必须由 Colab / GPU 正式运行产物确认。

### 2.4 T2SMark

- 原仓库入口候选: `run_sd35.py`, `src/inversion/inverse_diffusion3.py`, `src/t2s.py`。
- 当前优势: README 明确 SD3.5 Medium 需要 diffusers `0.32.0`, 且仓库已有 `run_sd35.py`。
- 建议: 优先建立 CEG observation adapter。

## 3. 补充表 baseline 适配判断

### 3.1 RivaGAN via invisible-watermark

- 原始视频 RivaGAN 管线已从本目录移除。
- 后续仅保留 `invisible-watermark` 中 `imwatermark/rivaGan.py` 作为图像补充 baseline。

### 3.2 WAM

- `watermark-anything` 支持图像水印 embedding、detection 和 bit decoding。
- 适合作为任意图像补充 baseline, 不应与扩散 latent watermark 主表混同解释。

### 3.3 TrustMark

- `trustmark/python` 提供 Python 入口。
- 适合作为任意分辨率图像水印补充 baseline。

## 4. 与 CEG paper_results 的关系

当前 `paper_results` 已能在没有 external baseline 时生成 CEG 主流程结果, 但 formal readiness 会因为缺少外部 baseline 而失败。后续需要先生成 external baseline archive, 再在 `colab_paper_results_pipeline.ipynb` 中配置 `BASELINE_RUN_ID`, 让结果包合并 baseline observations。
