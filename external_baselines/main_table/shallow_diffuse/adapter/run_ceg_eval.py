"""运行 Shallow Diffuse 的 CEG 外部 baseline 适配器。

该脚本属于外部 baseline 适配层。它抽取 Shallow Diffuse 的核心方法原语: 在扩散 latent 的
浅层/局部子空间写入水印模式, 生成图像后通过反演 latent 与目标 patch 的距离进行检测。
为接入 SD3.5 Medium, 该适配器使用 `(1, 16, height / 8, width / 8)` latent shape, 并以
可记录参数 `edit_fraction` 和 `preserve_non_watermark_channels` 表示浅层编辑强度。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external_baselines.main_table.sd35_diffusion_baseline_common import (  # noqa: E402
    as_text,
    build_observation,
    derive_threshold,
    image_to_tensor,
    load_json,
    load_prompt_rows,
    load_sd3_pipeline,
    row_id,
    safe_file_stem,
    split_name,
    write_json,
)
from main.analysis.attack_images import run_attack_workflow  # noqa: E402
from main.core.digest import build_stable_digest  # noqa: E402

BASELINE_ID = "shallow_diffuse"
PRODUCER_ID = "shallow_diffuse_sd35_ceg_adapter"
DEFAULT_SCORE_NAME = "negative_shallow_diffuse_patch_distance"


def _circle_mask(size: int, radius: int):
    """生成中心圆形 mask。"""

    import numpy as np

    x0 = y0 = size // 2
    y, x = np.ogrid[:size, :size]
    y = y[::-1]
    return ((x - x0) ** 2 + (y - y0) ** 2) <= radius**2


def _build_mask(shape: tuple[int, int, int, int], *, channel: int, radius: int, device: str):
    """构造浅层水印写入 mask。"""

    import torch

    if channel < -1 or channel >= shape[1]:
        raise ValueError(f"w_channel 必须在 [-1, {shape[1] - 1}] 范围内。")
    spatial_mask = torch.tensor(_circle_mask(shape[-1], radius), device=device, dtype=torch.bool)
    mask = torch.zeros(shape, device=device, dtype=torch.bool)
    if channel == -1:
        mask[:, :, spatial_mask] = True
    else:
        mask[:, channel, spatial_mask] = True
    return mask


def _build_patch(shape: tuple[int, int, int, int], *, pattern: str, radius: int, generator: Any, device: str):
    """构造 Shallow Diffuse 使用的 latent patch。"""

    import torch

    init = torch.randn(shape, generator=generator, device=device, dtype=torch.float32)
    if "complex" in pattern:
        patch = torch.fft.fftshift(torch.fft.fft2(init), dim=(-1, -2))
        if "zero" in pattern:
            return patch * 0
        if "ring" in pattern:
            source = patch.clone()
            for current_radius in range(radius, 0, -1):
                ring_mask = torch.tensor(_circle_mask(shape[-1], current_radius), device=device, dtype=torch.bool)
                for channel in range(shape[1]):
                    patch[:, channel, ring_mask] = source[0, channel, 0, current_radius].item()
            return patch
        return patch
    if "zero" in pattern:
        return init * 0
    return init


def _inject(latents: Any, mask: Any, patch: Any, *, injection: str):
    """向 latent 子空间写入水印 patch。"""

    import torch

    if "complex" in injection:
        latents_fft = torch.fft.fftshift(torch.fft.fft2(latents.float()), dim=(-1, -2))
        latents_fft[mask] = patch[mask].clone()
        return torch.fft.ifft2(torch.fft.ifftshift(latents_fft, dim=(-1, -2))).real.to(dtype=latents.dtype)
    result = latents.clone()
    result[mask] = patch.to(dtype=result.dtype)[mask].clone()
    return result


def _score_latents(reversed_latents: Any, mask: Any, patch: Any, *, measurement: str) -> float:
    """计算 Shallow Diffuse 检测分数, 分数越大越像阳性。"""

    import torch

    if "complex" in measurement:
        tested = torch.fft.fftshift(torch.fft.fft2(reversed_latents.float()), dim=(-1, -2))
        target = patch
    else:
        tested = reversed_latents
        target = patch.to(dtype=reversed_latents.dtype)
    distance = torch.abs(tested[mask] - target[mask]).mean().item()
    return -float(distance)


def _score_image(pipe: Any, image: Any, *, mask: Any, patch: Any, measurement: str, size: int, device: str, inversion_steps: int) -> float:
    """把图像反演到 latent 后计算 Shallow Diffuse 分数。"""

    tensor = image_to_tensor(image, size=size, device=device, dtype=pipe.vae.dtype)
    image_latents = pipe.get_image_latents(tensor, sample=False)
    reversed_latents = pipe.naive_forward_diffusion(image_latents, prompt="", num_inference_steps=inversion_steps, guidance_scale=1.0)
    return _score_latents(reversed_latents, mask, patch, measurement=measurement)


def run_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """执行 Shallow Diffuse SD3.5 适配流程。"""

    import torch
    from PIL import Image

    prompt_rows = load_prompt_rows(Path(args.prompt_plan))
    if args.max_samples is not None:
        prompt_rows = prompt_rows[: int(args.max_samples)]
    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    if args.require_cuda and device != "cuda":
        raise RuntimeError("Shallow Diffuse SD3.5 baseline 正式运行需要 CUDA GPU。")
    pipe = load_sd3_pipeline(model_id=args.model_id, device=device, torch_dtype_name=args.torch_dtype)

    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)

    latent_shape = (1, int(args.latent_channels), int(args.height) // 8, int(args.width) // 8)
    image_pairs: list[dict[str, Any]] = []
    observations_without_threshold: list[dict[str, Any]] = []
    states: dict[str, tuple[Any, Any]] = {}

    for index, row in enumerate(prompt_rows, start=1):
        prompt = as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        prompt_id = row_id(row, index, "prompt_id", "prompt")
        image_id = row_id(row, index, "image_id", "shallow_diffuse_image")
        file_stem = safe_file_stem(image_id, f"shallow_diffuse_image_{index:04d}")
        generator = torch.Generator(device=device).manual_seed(int(args.seed) + index - 1)
        patch_generator = torch.Generator(device=device).manual_seed(int(args.watermark_seed) + index - 1)
        clean_latents = torch.randn(latent_shape, generator=generator, device=device, dtype=pipe.transformer.dtype)
        mask = _build_mask(latent_shape, channel=int(args.w_channel), radius=int(args.w_radius), device=device)
        patch = _build_patch(latent_shape, pattern=args.w_pattern, radius=int(args.w_radius), generator=patch_generator, device=device)
        watermarked_latents = _inject(clean_latents.clone(), mask, patch, injection=args.w_injection)
        if args.preserve_non_watermark_channels:
            # Shallow Diffuse 原始流程强调只在受控浅层子空间中改变 latent。这里保留非 mask 区域,
            # 避免外部 baseline 适配器把方法退化为全 latent 替换。
            watermarked_latents = torch.where(mask, watermarked_latents, clean_latents)

        clean_image = pipe(prompt, guidance_scale=float(args.guidance_scale), num_inference_steps=int(args.num_inference_steps), height=int(args.height), width=int(args.width), latents=clean_latents).images[0]
        watermarked_image = pipe(prompt, guidance_scale=float(args.guidance_scale), num_inference_steps=int(args.num_inference_steps), height=int(args.height), width=int(args.width), latents=watermarked_latents).images[0]
        clean_path = clean_dir / f"{file_stem}_clean.png"
        watermarked_path = watermarked_dir / f"{file_stem}_shallow_diffuse.png"
        clean_image.save(clean_path)
        watermarked_image.save(watermarked_path)

        clean_score = _score_image(pipe, clean_image, mask=mask, patch=patch, measurement=args.w_measurement, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
        watermarked_score = _score_image(pipe, watermarked_image, mask=mask, patch=patch, measurement=args.w_measurement, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
        states[image_id] = (mask, patch)
        pair = {
            "event_id": image_id,
            "image_id": image_id,
            "prompt_id": prompt_id,
            "prompt_text": prompt,
            "split": split_name(row),
            "clean_image_path": str(clean_path),
            "watermarked_image_path": str(watermarked_path),
            "baseline_id": BASELINE_ID,
            "generation_model_id": args.model_id,
            "latent_shape": list(latent_shape),
        }
        image_pairs.append(pair)
        for sample_role, score in (("clean_negative", clean_score), ("positive_source", watermarked_score)):
            observations_without_threshold.append(
                build_observation(
                    baseline_id=BASELINE_ID,
                    score_name=DEFAULT_SCORE_NAME,
                    producer_id=PRODUCER_ID,
                    event_id=f"{image_id}__{sample_role}",
                    score=score,
                    threshold=0.0,
                    threshold_source="pending",
                    row=row,
                    index=index,
                    sample_role=sample_role,
                    attack_family="clean",
                    attack_condition="clean_none",
                    image_id=image_id,
                )
            )
        if device == "cuda":
            torch.cuda.empty_cache()

    threshold, threshold_source = derive_threshold(observations_without_threshold, args.threshold)
    observations = []
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
        attacked_manifest = load_json(attacked_manifest_path)
        for attack_index, record in enumerate(attacked_manifest.get("attacked_images", []), start=1):
            source_id = as_text(record.get("source_image_id"))
            source_pair = next((item for item in image_pairs if item["image_id"] == source_id), None)
            state = states.get(source_id)
            if source_pair is None or state is None:
                continue
            mask, patch = state
            with Image.open(Path(as_text(record.get("attacked_image_path")))) as attacked_image:
                score = _score_image(pipe, attacked_image, mask=mask, patch=patch, measurement=args.w_measurement, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
            obs = build_observation(
                baseline_id=BASELINE_ID,
                score_name=DEFAULT_SCORE_NAME,
                producer_id=PRODUCER_ID,
                event_id=as_text(record.get("attacked_image_id"), f"attacked_{attack_index:04d}"),
                score=score,
                threshold=threshold,
                threshold_source=threshold_source,
                row=source_pair,
                index=attack_index,
                sample_role=as_text(record.get("sample_role"), "attacked_positive"),
                attack_family=as_text(record.get("attack_family"), "unknown_attack"),
                attack_condition=as_text(record.get("attack_condition"), "unknown_attack_condition"),
                image_id=source_id,
            )
            obs["final_decision"] = bool(score >= threshold)
            observations.append(obs)
            if device == "cuda":
                torch.cuda.empty_cache()

    write_json(artifact_root / "image_pairs_shallow_diffuse.json", image_pairs)
    manifest = {
        "artifact_name": "shallow_diffuse_sd35_ceg_adapter_manifest.json",
        "producer_id": PRODUCER_ID,
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
            "w_injection": args.w_injection,
            "w_measurement": args.w_measurement,
            "edit_fraction": float(args.edit_fraction),
            "preserve_non_watermark_channels": bool(args.preserve_non_watermark_channels),
        },
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest({"baseline_id": BASELINE_ID, "prompt_count": len(prompt_rows), "observation_count": len(observations)}),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 Shallow Diffuse SD3.5 CEG baseline adapter。")
    parser.add_argument("--prompt-plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--model-id", default="stabilityai/stable-diffusion-3.5-medium")
    parser.add_argument("--torch-dtype", default="float16")
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--latent-channels", type=int, default=16)
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--num-inversion-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--watermark-seed", type=int, default=42)
    parser.add_argument("--w-channel", type=int, default=0)
    parser.add_argument("--w-radius", type=int, default=10)
    parser.add_argument("--w-pattern", default="complex_rand", choices=["complex_rand", "complex_ring", "complex_zero", "seed_rand", "seed_zero"])
    parser.add_argument("--w-injection", default="complex", choices=["complex", "seed"])
    parser.add_argument("--w-measurement", default="l1_complex")
    parser.add_argument("--edit-fraction", type=float, default=0.2)
    parser.add_argument("--preserve-non-watermark-channels", action="store_true", default=True)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    observations, manifest = run_adapter(args)
    output_path = Path(args.out)
    write_json(output_path, observations)
    manifest["baseline_observations_path"] = str(output_path)
    write_json(output_path.with_name("shallow_diffuse_sd35_ceg_adapter_manifest.json"), manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
