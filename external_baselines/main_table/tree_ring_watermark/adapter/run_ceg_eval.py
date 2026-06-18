"""运行 Tree-Ring 的 CEG 外部 baseline 适配器。

该脚本位于 `external_baselines/`, 属于论文实验适配层, 不进入 CEG 主方法层。
它参考 Tree-Ring 的核心方法原语: 在扩散初始 latent 的傅里叶域中心区域写入环形 key,
生成图像后通过扩散反演恢复 latent, 再计算恢复 latent 与 key 的距离。为接入 SD3.5 Medium,
该适配器把原始 SD2 latent 形状 `(1, 4, 64, 64)` 显式推广为 SD3.5 常用的
`(1, 16, height / 8, width / 8)`。

重要边界:
- 该脚本会在 GPU 环境真实调用 diffusers 模型, 不是 dry-run 结果生成器。
- 该脚本只输出 CEG 统一的 baseline observations 和外部 baseline 自身图像产物。
- 该脚本不调用 CEG-WM 项目, 也不把 Tree-Ring 逻辑写入 `main/methods/ceg/`。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.attack_images import run_attack_workflow  # noqa: E402
from main.core.digest import build_stable_digest  # noqa: E402

BASELINE_ID = "tree_ring"
DEFAULT_SCORE_NAME = "negative_tree_ring_fft_key_distance"


def _load_json(path: str | Path) -> Any:
    """读取 JSON 文件, 使用 utf-8-sig 兼容 Windows 或 Colab 产生的 BOM。"""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 供后续论文流程读取。"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _as_text(value: Any, default: str = "") -> str:
    """把可选字段规范化为去空白字符串。"""

    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _load_prompt_rows(path: Path) -> list[dict[str, Any]]:
    """读取 CEG prompt plan, 支持 list 或包含 prompts/items/records/prompt_rows 的 object。"""

    payload = _load_json(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for field_name in ("prompts", "items", "records", "prompt_rows"):
            candidate = payload.get(field_name)
            if isinstance(candidate, list):
                rows = candidate
                break
        if rows is None:
            raise ValueError("prompt plan object 必须包含 prompts/items/records/prompt_rows 列表字段。")
    else:
        raise TypeError("prompt plan 必须是 JSON list 或 object。")

    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise TypeError(f"prompt plan 第 {index} 行必须是 object。")
        prompt_text = _as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        if not prompt_text:
            raise ValueError(f"prompt plan 第 {index} 行缺少 prompt_text/prompt/text。")
        normalized.append(dict(row))
    if not normalized:
        raise ValueError("prompt plan 不能为空。")
    return normalized


def _safe_file_stem(value: str, fallback: str) -> str:
    """把 image_id 转为安全文件名主干。"""

    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value).strip("._")
    return candidate or fallback


def _row_id(row: dict[str, Any], index: int, field_name: str, fallback_prefix: str) -> str:
    """读取 prompt_id/image_id, 缺失时使用稳定序号。"""

    return _as_text(row.get(field_name), f"{fallback_prefix}_{index:04d}")


def _split(row: dict[str, Any]) -> str:
    """读取 split, 缺失时默认归入 test。"""

    return _as_text(row.get("split"), "test")


def _circle_mask(size: int, radius: int, *, x_offset: int = 0, y_offset: int = 0):
    """生成 Tree-Ring 使用的傅里叶域圆形中心 mask。"""

    import numpy as np

    x0 = size // 2 + x_offset
    y0 = size // 2 + y_offset
    y, x = np.ogrid[:size, :size]
    y = y[::-1]
    return ((x - x0) ** 2 + (y - y0) ** 2) <= radius**2


def _build_watermark_key(shape: tuple[int, int, int, int], *, pattern: str, radius: int, generator: Any, device: str):
    """构造 Tree-Ring 傅里叶域 key。

    通用写法是把 key 构造与注入逻辑分离, 便于以后复用到不同 latent 形状。
    项目特定写法是默认使用 ring/rand/zeros 三类模式, 与 Tree-Ring 原始实现保持对应。
    """

    import torch

    init = torch.randn(shape, generator=generator, device=device, dtype=torch.float32)
    patch = torch.fft.fftshift(torch.fft.fft2(init), dim=(-1, -2))
    if "zeros" in pattern:
        patch = patch * 0
    elif "ring" in pattern:
        source = patch.clone().detach()
        latent_size = shape[-1]
        for current_radius in range(radius, 0, -1):
            ring_mask = torch.tensor(_circle_mask(latent_size, current_radius), device=device, dtype=torch.bool)
            for channel in range(shape[1]):
                patch[:, channel, ring_mask] = source[0, channel, 0, current_radius].item()
    elif "rand" in pattern:
        patch[:] = patch[0]
    else:
        raise ValueError(f"unsupported Tree-Ring pattern: {pattern}")
    # Tree-Ring 原始方法在傅里叶域保存复数 key。这里必须保留 complex dtype,
    # 否则会丢失虚部, 使后续 latent 注入和距离检测不再等价于原始 Tree-Ring。
    return patch


def _build_watermark_mask(shape: tuple[int, int, int, int], *, channel: int, radius: int, device: str):
    """构造 Tree-Ring 写入区域 mask。"""

    import torch

    if channel < -1 or channel >= shape[1]:
        raise ValueError(f"w_channel 必须在 [-1, {shape[1] - 1}] 范围内。")
    latent_size = shape[-1]
    torch_mask = torch.tensor(_circle_mask(latent_size, radius), device=device, dtype=torch.bool)
    mask = torch.zeros(shape, device=device, dtype=torch.bool)
    if channel == -1:
        mask[:, :, torch_mask] = True
    else:
        mask[:, channel, torch_mask] = True
    return mask


def _inject_watermark(latents: Any, mask: Any, key: Any):
    """在 latent 傅里叶域写入 Tree-Ring key。"""

    import torch

    latents_fft = torch.fft.fftshift(torch.fft.fft2(latents.float()), dim=(-1, -2))
    latents_fft[mask] = key[mask].clone()
    return torch.fft.ifft2(torch.fft.ifftshift(latents_fft, dim=(-1, -2))).real.to(dtype=latents.dtype)


def _score_latents(reversed_latents: Any, mask: Any, key: Any) -> float:
    """计算 CEG 统一使用的 Tree-Ring 检测分数。

    Tree-Ring 原始距离越小越像阳性。CEG baseline observation 约定默认使用
    `higher_is_positive=True`, 因此这里返回负距离, 使分数越大越像阳性。
    """

    import torch

    reversed_fft = torch.fft.fftshift(torch.fft.fft2(reversed_latents.float()), dim=(-1, -2))
    distance = torch.abs(reversed_fft[mask] - key[mask]).mean().item()
    return -float(distance)


def _image_to_tensor(image: Any, *, size: int, device: str, dtype: Any):
    """把 PIL 图像转换为 SD VAE 输入张量, 范围为 [-1, 1]。"""

    import numpy as np
    import torch
    from PIL import Image

    resized = image.convert("RGB").resize((size, size), Image.Resampling.BICUBIC)
    array = np.asarray(resized).astype("float32") / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
    tensor = tensor * 2.0 - 1.0
    return tensor.to(device=device, dtype=dtype)


class _InversionStableDiffusion3PipelineMixin:
    """为 StableDiffusion3Pipeline 增加轻量反演方法。

    该实现属于外部 baseline 适配代码, 用于让 Tree-Ring 在 SD3.5 latent 形状上得到
    可检测分数。它不属于 CEG 主方法创新点。
    """

    def get_image_latents(self, image: Any, *, sample: bool = False):
        """通过 VAE 编码图像得到 latent。"""

        encoding_dist = self.vae.encode(image).latent_dist
        encoding = encoding_dist.sample() if sample else encoding_dist.mode()
        # SD3 系列 VAE 通常同时声明 scaling_factor 和 shift_factor。
        # 这里显式读取 shift_factor, 使反演 latent 与 diffusers SD3 pipeline 的
        # 图像编码约定保持一致；旧 VAE 没有该字段时自然退化为 0。
        shift_factor = float(getattr(self.vae.config, "shift_factor", 0.0) or 0.0)
        scaling_factor = float(getattr(self.vae.config, "scaling_factor", 1.0) or 1.0)
        return (encoding - shift_factor) * scaling_factor

    def naive_forward_diffusion(self, latents: Any, *, prompt: str = "", num_inference_steps: int = 5, guidance_scale: float = 1.0):
        """使用 SD3 scheduler 近似执行反向扩散的逆过程。"""

        import torch

        self.scheduler.set_timesteps(num_inference_steps, device=self._execution_device)
        do_classifier_free_guidance = guidance_scale > 1.0
        prompt_embeds, _, pooled_projections, _ = self.encode_prompt(
            prompt=prompt,
            prompt_2=None,
            prompt_3=None,
            device=self._execution_device,
            do_classifier_free_guidance=do_classifier_free_guidance,
        )
        timesteps = self.scheduler.timesteps
        for index, timestep in enumerate(reversed(timesteps)):
            latent_model_input = torch.cat([latents] * 2) if do_classifier_free_guidance else latents
            timestep_tensor = timestep.expand(latent_model_input.shape[0])
            noise_pred = self.transformer(
                latent_model_input,
                timestep=timestep_tensor,
                pooled_projections=pooled_projections,
                encoder_hidden_states=prompt_embeds,
                return_dict=False,
            )[0]
            if do_classifier_free_guidance:
                noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
                noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)
            latents = latents - (self.scheduler.sigmas[index + 1] - self.scheduler.sigmas[index]) * noise_pred
        return latents


def _load_sd3_pipeline(*, model_id: str, device: str, torch_dtype_name: str):
    """加载 SD3.5 pipeline, 并动态组合反演 mixin。"""

    import torch
    from diffusers import StableDiffusion3Pipeline

    dtype_lookup = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    torch_dtype = dtype_lookup.get(torch_dtype_name.lower(), torch.float16)
    PipelineClass = type("TreeRingInversionStableDiffusion3Pipeline", (_InversionStableDiffusion3PipelineMixin, StableDiffusion3Pipeline), {})
    pipe = PipelineClass.from_pretrained(model_id, torch_dtype=torch_dtype)
    pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    return pipe


def _build_observation(
    *,
    event_id: str,
    score: float,
    threshold: float,
    threshold_source: str,
    row: dict[str, Any],
    index: int,
    sample_role: str,
    attack_family: str,
    attack_condition: str,
    image_id: str,
) -> dict[str, Any]:
    """构造一条 CEG baseline observation。"""

    return {
        "event_id": event_id,
        "baseline_id": BASELINE_ID,
        "score": float(score),
        "threshold": float(threshold),
        "score_name": DEFAULT_SCORE_NAME,
        "higher_is_positive": True,
        "split": _split(row),
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "prompt_id": _row_id(row, index, "prompt_id", "prompt"),
        "image_id": image_id,
        "producer_id": "tree_ring_sd35_ceg_adapter",
        "producer_role": "external_baseline_sd35_adapter",
        "formal_result_claim": False,
        "threshold_source": threshold_source,
    }


def _derive_threshold(observations: Iterable[dict[str, Any]], explicit_threshold: float | None) -> tuple[float, str]:
    """从 calibration split 派生阈值, 或使用显式阈值。"""

    if explicit_threshold is not None:
        return float(explicit_threshold), "cli_threshold"
    negative_scores: list[float] = []
    positive_scores: list[float] = []
    for row in observations:
        if row.get("split") != "calibration":
            continue
        if row.get("sample_role") == "clean_negative":
            negative_scores.append(float(row["score"]))
        elif row.get("sample_role") == "positive_source":
            positive_scores.append(float(row["score"]))
    if negative_scores and positive_scores:
        return (max(negative_scores) + min(positive_scores)) / 2.0, "calibration_midpoint_between_negative_max_and_positive_min"
    return 0.0, "fallback_zero_no_calibration_pairs"


def run_tree_ring_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """执行 Tree-Ring SD3.5 适配流程并返回 observations 与 manifest。"""

    import torch

    prompt_rows = _load_prompt_rows(Path(args.prompt_plan))
    if args.max_samples is not None:
        prompt_rows = prompt_rows[: int(args.max_samples)]

    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    if args.require_cuda and device != "cuda":
        raise RuntimeError("Tree-Ring SD3.5 baseline 正式运行需要 CUDA GPU。")
    pipe = _load_sd3_pipeline(model_id=args.model_id, device=device, torch_dtype_name=args.torch_dtype)

    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)

    latent_shape = (1, int(args.latent_channels), int(args.height) // 8, int(args.width) // 8)
    observations_without_threshold: list[dict[str, Any]] = []
    image_pairs: list[dict[str, Any]] = []

    for index, row in enumerate(prompt_rows, start=1):
        prompt = _as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        prompt_id = _row_id(row, index, "prompt_id", "prompt")
        image_id = _row_id(row, index, "image_id", "tree_ring_image")
        file_stem = _safe_file_stem(image_id, f"tree_ring_image_{index:04d}")
        generator = torch.Generator(device=device).manual_seed(int(args.seed) + index - 1)

        clean_latents = torch.randn(latent_shape, generator=generator, device=device, dtype=pipe.transformer.dtype)
        key_generator = torch.Generator(device=device).manual_seed(int(args.watermark_seed))
        key = _build_watermark_key(
            latent_shape,
            pattern=args.w_pattern,
            radius=int(args.w_radius),
            generator=key_generator,
            device=device,
        )
        mask = _build_watermark_mask(latent_shape, channel=int(args.w_channel), radius=int(args.w_radius), device=device)
        watermarked_latents = _inject_watermark(clean_latents.clone(), mask, key)

        clean_image = pipe(
            prompt,
            guidance_scale=float(args.guidance_scale),
            num_inference_steps=int(args.num_inference_steps),
            height=int(args.height),
            width=int(args.width),
            latents=clean_latents,
        ).images[0]
        watermarked_image = pipe(
            prompt,
            guidance_scale=float(args.guidance_scale),
            num_inference_steps=int(args.num_inference_steps),
            height=int(args.height),
            width=int(args.width),
            latents=watermarked_latents,
        ).images[0]

        clean_path = clean_dir / f"{file_stem}_clean.png"
        watermarked_path = watermarked_dir / f"{file_stem}_tree_ring.png"
        clean_image.save(clean_path)
        watermarked_image.save(watermarked_path)

        clean_tensor = _image_to_tensor(clean_image, size=int(args.height), device=device, dtype=pipe.vae.dtype)
        watermarked_tensor = _image_to_tensor(watermarked_image, size=int(args.height), device=device, dtype=pipe.vae.dtype)
        clean_image_latents = pipe.get_image_latents(clean_tensor, sample=False)
        watermarked_image_latents = pipe.get_image_latents(watermarked_tensor, sample=False)
        reversed_clean = pipe.naive_forward_diffusion(
            clean_image_latents,
            prompt="",
            num_inference_steps=int(args.num_inversion_steps),
            guidance_scale=1.0,
        )
        reversed_watermarked = pipe.naive_forward_diffusion(
            watermarked_image_latents,
            prompt="",
            num_inference_steps=int(args.num_inversion_steps),
            guidance_scale=1.0,
        )
        clean_score = _score_latents(reversed_clean, mask, key)
        watermarked_score = _score_latents(reversed_watermarked, mask, key)

        pair = {
            "event_id": image_id,
            "image_id": image_id,
            "prompt_id": prompt_id,
            "prompt_text": prompt,
            "split": _split(row),
            "clean_image_path": str(clean_path),
            "watermarked_image_path": str(watermarked_path),
            "baseline_id": BASELINE_ID,
            "generation_model_id": args.model_id,
            "latent_shape": list(latent_shape),
        }
        image_pairs.append(pair)
        observations_without_threshold.append(
            _build_observation(
                event_id=f"{image_id}__clean_negative",
                score=clean_score,
                threshold=0.0,
                threshold_source="pending",
                row=row,
                index=index,
                sample_role="clean_negative",
                attack_family="clean",
                attack_condition="clean_none",
                image_id=image_id,
            )
        )
        observations_without_threshold.append(
            _build_observation(
                event_id=f"{image_id}__positive_source",
                score=watermarked_score,
                threshold=0.0,
                threshold_source="pending",
                row=row,
                index=index,
                sample_role="positive_source",
                attack_family="clean",
                attack_condition="clean_none",
                image_id=image_id,
            )
        )

    threshold, threshold_source = _derive_threshold(observations_without_threshold, args.threshold)
    observations: list[dict[str, Any]] = []
    for row in observations_without_threshold:
        updated = dict(row)
        updated["threshold"] = threshold
        updated["threshold_source"] = threshold_source
        updated["final_decision"] = bool(float(updated["score"]) >= threshold)
        observations.append(updated)

    attack_families = [item.strip() for item in str(args.attack_families or "").split(",") if item.strip()]
    attacked_manifest_path: str | None = None
    if attack_families:
        attack_root = artifact_root / "attacks"
        run_attack_workflow(image_pairs, attack_root, attack_families=attack_families)
        attacked_manifest_path = str(attack_root / "image_manifests" / "attacked_image_manifest.json")
        attacked_manifest = _load_json(attacked_manifest_path)
        for attack_index, record in enumerate(attacked_manifest.get("attacked_images", []), start=1):
            if not isinstance(record, dict):
                continue
            source_id = _as_text(record.get("source_image_id"))
            source_pair = next((item for item in image_pairs if item["image_id"] == source_id), None)
            if source_pair is None:
                continue
            attacked_path = Path(_as_text(record.get("attacked_image_path")))
            with __import__("PIL.Image", fromlist=["Image"]).open(attacked_path) as attacked_image:
                attacked_tensor = _image_to_tensor(attacked_image, size=int(args.height), device=device, dtype=pipe.vae.dtype)
            attacked_latents = pipe.get_image_latents(attacked_tensor, sample=False)
            reversed_attacked = pipe.naive_forward_diffusion(
                attacked_latents,
                prompt="",
                num_inference_steps=int(args.num_inversion_steps),
                guidance_scale=1.0,
            )
            # 攻击样本复用同一批 key 和 mask 的统计形状。正式大规模运行时每张图的 key 可记录到 manifest 后再逐张恢复。
            score = _score_latents(reversed_attacked, mask, key)
            sample_role = _as_text(record.get("sample_role"), "attacked_positive")
            obs = _build_observation(
                event_id=_as_text(record.get("attacked_image_id"), f"attacked_{attack_index:04d}"),
                score=score,
                threshold=threshold,
                threshold_source=threshold_source,
                row=source_pair,
                index=attack_index,
                sample_role=sample_role,
                attack_family=_as_text(record.get("attack_family"), "unknown_attack"),
                attack_condition=_as_text(record.get("attack_condition"), "unknown_attack_condition"),
                image_id=source_id,
            )
            obs["final_decision"] = bool(score >= threshold)
            observations.append(obs)

    _write_json(artifact_root / "image_pairs_tree_ring.json", image_pairs)
    manifest = {
        "artifact_name": "tree_ring_sd35_ceg_adapter_manifest.json",
        "producer_id": "tree_ring_sd35_ceg_adapter",
        "baseline_id": BASELINE_ID,
        "model_id": args.model_id,
        "prompt_plan_path": str(Path(args.prompt_plan)),
        "artifact_root": str(artifact_root),
        "image_pair_count": len(image_pairs),
        "observation_count": len(observations),
        "latent_shape": list(latent_shape),
        "watermark_parameters": {
            "w_channel": int(args.w_channel),
            "w_radius": int(args.w_radius),
            "w_pattern": args.w_pattern,
            "watermark_seed": int(args.watermark_seed),
        },
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest(
            {
                "baseline_id": BASELINE_ID,
                "model_id": args.model_id,
                "prompt_count": len(prompt_rows),
                "observation_count": len(observations),
                "latent_shape": list(latent_shape),
                "threshold": threshold,
            }
        ),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 Tree-Ring SD3.5 CEG baseline adapter。")
    parser.add_argument("--prompt-plan", required=True, help="CEG prompt plan JSON 路径。")
    parser.add_argument("--out", required=True, help="输出 baseline observations JSON 路径。")
    parser.add_argument("--artifact-root", default=None, help="Tree-Ring 图像和 manifest 输出目录。默认使用 --out 的父目录。")
    parser.add_argument("--model-id", default="stabilityai/stable-diffusion-3.5-medium", help="Hugging Face 模型 ID。")
    parser.add_argument("--torch-dtype", default="float16", help="模型 dtype, 例如 float16/bfloat16/float32。")
    parser.add_argument("--height", type=int, default=512, help="生成图像高度。")
    parser.add_argument("--width", type=int, default=512, help="生成图像宽度。")
    parser.add_argument("--latent-channels", type=int, default=16, help="SD3.5 latent 通道数。")
    parser.add_argument("--num-inference-steps", type=int, default=28, help="生成采样步数。")
    parser.add_argument("--num-inversion-steps", type=int, default=28, help="反演步数。")
    parser.add_argument("--guidance-scale", type=float, default=7.0, help="生成 guidance scale。")
    parser.add_argument("--seed", type=int, default=0, help="样本生成随机种子。")
    parser.add_argument("--watermark-seed", type=int, default=999999, help="Tree-Ring key 随机种子。")
    parser.add_argument("--w-channel", type=int, default=0, help="写入通道, -1 表示全部通道。")
    parser.add_argument("--w-radius", type=int, default=10, help="傅里叶域写入半径。")
    parser.add_argument("--w-pattern", default="ring", choices=["ring", "rand", "zeros"], help="Tree-Ring key 模式。")
    parser.add_argument("--threshold", type=float, default=None, help="显式阈值。缺失时从 calibration 样本派生。")
    parser.add_argument("--attack-families", default="", help="逗号分隔攻击族, 例如 jpeg,rotate。为空则只评估 clean。")
    parser.add_argument("--max-samples", type=int, default=None, help="最多读取多少条 prompt, 便于 probe。")
    parser.add_argument("--force-cpu", action="store_true", help="强制使用 CPU, 仅用于小规模调试。")
    parser.add_argument("--require-cuda", action="store_true", help="要求 CUDA, 正式 baseline 推荐启用。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    observations, manifest = run_tree_ring_adapter(args)
    output_path = Path(args.out)
    _write_json(output_path, observations)
    manifest["baseline_observations_path"] = str(output_path)
    manifest_path = output_path.with_name("tree_ring_sd35_ceg_adapter_manifest.json")
    _write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
