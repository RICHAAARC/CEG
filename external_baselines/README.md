# External Baseline Intake And Adaptation Plan

该目录保存外部 baseline 的本地代码快照、入口检查记录和后续适配计划。此处代码只用于论文实验对比和外部命令封装, 不进入 `main/` 主方法层。

## 1. 目录边界

- `main_table/`: 主表候选 baseline, 与 CEG 在同一主结果表中对比。
- `supplementary_table/`: 补充表候选 baseline, 用于图像水印或通用水印补充对比。
- `adaptation_notes/`: 适配说明, 记录 inversion、latent shape、SD3.5 Medium 和输入输出契约差异。
- `plans/`: 后续生成 `baseline_plan.json` 或外部运行命令模板的位置。

通用工程写法是把第三方仓库作为外部命令执行对象隔离管理。项目特定写法是 CEG 只读取统一的 `baseline_observations.json`, 不在主方法层直接依赖第三方实现。

## 2. 主表 baseline

| baseline | 本地路径 | 上游仓库 | 当前检查结论 | 适配重点 |
|---|---|---|---|---|
| Tree-Ring | `main_table/tree_ring_watermark/source` | https://github.com/YuxinWenRick/tree-ring-watermark | 已拉取代码, README 明确依赖扩散 inversion 检测初始噪声 key | 需要重做 SD3.5 Medium inversion 入口, 对齐 latent shape 和 scheduler |
| Gaussian Shading | `main_table/gaussian_shading/source` | https://github.com/bsmhmmlf/Gaussian-Shading | 已拉取代码, README 明确原始兼容 SD 1.4/2.0/2.1 且 latent size 为 `4 x 64 x 64` | 需要重做 SD3.5 Medium 参数、watermark capacity 和 inversion 适配 |
| Shallow Diffuse | `main_table/shallow_diffuse/source` | https://github.com/liwd190019/Shallow-Diffuse | 已拉取代码, README 提示高版本 diffusers 可能不兼容 DDIM inversion | 需要重做 inversion、latent shape 和 SD3.5 Medium 采样流程适配 |
| T2SMark | `main_table/t2smark/source` | https://github.com/0xD009/T2SMark | 已拉取代码, 仓库包含 `run_sd35.py`, README 明确 SD3.5 Medium 需要 diffusers `0.32.0` | 优先作为 SD3.5 Medium 主表 baseline 接入 |
| CEG | `main/` 与 `scripts/run_colab_paper_results_pipeline.py` | 本仓库 | 已有主流程和 `TPR@FPR` 统计 | 作为 proposed method, 不放入 external baseline 命令计划 |

## 3. 补充表 baseline

| baseline | 本地路径 | 上游仓库 | 当前检查结论 | 适配重点 |
|---|---|---|---|---|
| RivaGAN via invisible-watermark | `supplementary_table/rivagan_invisible_watermark/source` | https://github.com/ShieldMnt/invisible-watermark | 已拉取图像水印实现, 包含 `imwatermark/rivaGan.py` | 建议用于图像补充 baseline, 输出统一 observation |
| WAM | `supplementary_table/watermark_anything/source` | https://github.com/facebookresearch/watermark-anything | 已拉取代码, README 包含 embedding、detection 和 bit decoding 示例 | 作为任意图像水印补充表 baseline |
| TrustMark | `supplementary_table/trustmark/source` | https://github.com/adobe/trustmark | 已拉取代码, Python 子目录包含 TrustMark 入口说明 | 作为任意分辨率图像水印补充表 baseline |

## 4. 内部消融需求

内部消融属于 CEG 方法自身, 不应放入 external baseline 命令计划。后续应在 `main/methods/ceg/ablations.py` 与结果表配置中补齐或重命名下列版本:

| 消融项 | 论文目的 | 是否正式方法版本 |
|---|---|---|
| CEG w/o geometry | 证明几何链是否带来 rescue 增益 | 是 |
| CEG w/o content-adaptive routing | 证明内容自适应区域路由是否必要 | 是 |
| CEG LF-only | 证明低频链在 clean / mild attack 下的稳定性 | 是 |
| CEG HF-only | 证明纹理区高频链在强扰动下的贡献 | 是 |
| CEG random routing | 排除“区域选择只是随机增强”的解释 | 是 |
| CEG saliency-only | 检查语义显著性是否足以支撑鲁棒性 | 是 |
| CEG texture-only | 检查纹理复杂度是否足以支撑鲁棒性 | 是 |
| CEG w/o attestation | 证明 final-level attestation 对误报控制的作用 | 是 |
| content score direct threshold | 作为基础检测链 | 是 |
| geometry direct positive | 只作为错误机制诊断 | 否, 不进入正式主表方法版本 |

## 5. 后续接入顺序

1. 先为每个外部 baseline 建立统一 adapter, 输出 `baseline_observations.json`。
2. T2SMark 优先接入主表, 因为它已有 SD3.5 Medium 入口。
3. Tree-Ring、Gaussian Shading、Shallow Diffuse 需要先完成 SD3.5 Medium inversion 与 latent shape 适配, 再进入正式主表。
4. invisible-watermark RivaGAN、WAM、TrustMark 作为图像域补充 baseline, 不与扩散 latent watermark 主表混为同一机制解释。
5. 所有正式 baseline 运行证据必须由 `baseline_execution_manifest.json` 和 evidence paths 绑定, 否则只能作为 dry-run 或 pilot 对比。
