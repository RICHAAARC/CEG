# External Baseline SD3.5 Medium Adaptation Notes

## 1. 共同输入输出契约

外部 baseline 后续都应适配为相同的命令形态:

```bash
python external_baselines/<group>/<baseline>/adapter/run_ceg_eval.py \
  --image-pairs <image_pairs.json> \
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
- 当前风险: 原实现围绕早期 Stable Diffusion 与 DDIM inversion, 不能直接假设适配 SD3.5 Medium。
- 必须补充: SD3.5 Medium latent shape、scheduler、text encoder 条件、inversion 过程和检测 key shape。

### 2.2 Gaussian Shading

- 原仓库入口候选: `run_gaussian_shading.py`, `watermark.py`, `inverse_stable_diffusion.py`。
- 当前风险: README 指出原兼容 SD 1.4/2.0/2.1, latent space size 为 `4 x 64 x 64`。
- 必须补充: SD3.5 Medium latent shape 参数、bit capacity、`channel_copy` / `hw_copy` 与 inversion 适配。

### 2.3 Shallow Diffuse

- 原仓库入口候选: `run_shallow_diffuse_t2i.py`, `run_shallow_diffuse_i2i.py`, `inverse_stable_diffusion.py`。
- 当前风险: README 提示高版本 diffusers 可能不兼容原 DDIM inversion。
- 必须补充: SD3.5 Medium inversion、latent subspace 构造和检测统计对齐。

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
