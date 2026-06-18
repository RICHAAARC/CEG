"""运行 Gaussian Shading 的 CEG 外部 baseline 适配器。

该脚本属于外部 baseline 适配层, 不进入 CEG 主方法层。它参考 Gaussian Shading 的核心
方法原语: 用二值 message 控制高斯 latent 的截断采样区间, 生成图像后通过扩散反演恢复
latent, 再用符号解码和重复投票得到 watermark bit accuracy。为接入 SD3.5 Medium, 该实现
将原始 `(1, 4, 64, 64)` latent 显式推广为 `(1, 16, height / 8, width / 8)`。
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

BASELINE_ID = "gaussian_shading"
PRODUCER_ID = "gaussian_shading_sd35_ceg_adapter"
DEFAULT_SCORE_NAME = "gaussian_shading_bit_accuracy"


class GaussianShadingState:
    """保存单张图像的 Gaussian Shading key 和 message。"""

    def __init__(self, *, shape: tuple[int, int, int, int], channel_copy: int, hw_copy: int, device: str, generator: Any):
        """初始化与 SD3.5 latent shape 对齐的重复投票结构。"""

        import torch

        if shape[1] % channel_copy != 0 or shape[2] % hw_copy != 0 or shape[3] % hw_copy != 0:
            raise ValueError("latent shape 必须能被 channel_copy 和 hw_copy 整除。")
        self.shape = shape
        self.channel_copy = int(channel_copy)
        self.hw_copy = int(hw_copy)
        self.device = device
        self.key = torch.randint(0, 2, shape, generator=generator, device=device, dtype=torch.int64)
        self.watermark = torch.randint(
            0,
            2,
            (shape[0], shape[1] // channel_copy, shape[2] // hw_copy, shape[3] // hw_copy),
            generator=generator,
            device=device,
            dtype=torch.int64,
        )
        self.threshold = 1 if channel_copy == 1 and hw_copy == 1 else channel_copy * hw_copy * hw_copy // 2

    def _expanded_message(self):
        """把低维 watermark message 重复到完整 latent shape。"""

        return self.watermark.repeat(1, self.channel_copy, self.hw_copy, self.hw_copy)

    def create_watermarked_latents(self, *, generator: Any, dtype: Any):
        """按 message bit 的截断高斯区间采样 watermarked latent。"""

        import torch

        message = ((self._expanded_message() + self.key) % 2).to(torch.float32)
        eps = 1e-6
        random_unit = torch.rand(self.shape, generator=generator, device=self.device, dtype=torch.float32)
        # bit=0 对应负半轴截断高斯, bit=1 对应正半轴截断高斯。
        cdf_value = torch.where(message > 0.5, 0.5 + 0.5 * random_unit, 0.5 * random_unit)
        cdf_value = torch.clamp(cdf_value, eps, 1.0 - eps)
        latent = torch.sqrt(torch.tensor(2.0, device=self.device)) * torch.erfinv(2.0 * cdf_value - 1.0)
        return latent.to(dtype=dtype)

    def score(self, reversed_latents: Any) -> float:
        """对反演 latent 解码并计算 bit accuracy。"""

        import torch

        reversed_m = (reversed_latents > 0).to(torch.int64)
        reversed_sd = (reversed_m + self.key) % 2
        ch_stride = self.shape[1] // self.channel_copy
        h_stride = self.shape[2] // self.hw_copy
        w_stride = self.shape[3] // self.hw_copy
        split_dim1 = torch.cat(torch.split(reversed_sd, [ch_stride] * self.channel_copy, dim=1), dim=0)
        split_dim2 = torch.cat(torch.split(split_dim1, [h_stride] * self.hw_copy, dim=2), dim=0)
        split_dim3 = torch.cat(torch.split(split_dim2, [w_stride] * self.hw_copy, dim=3), dim=0)
        vote = torch.sum(split_dim3, dim=0)
        decoded = (vote > self.threshold).to(torch.int64)
        return float((decoded == self.watermark).float().mean().item())


def _score_image(pipe: Any, image: Any, *, state: GaussianShadingState, size: int, device: str, inversion_steps: int) -> float:
    """把图像反演到 latent 后计算 Gaussian Shading 分数。"""

    tensor = image_to_tensor(image, size=size, device=device, dtype=pipe.vae.dtype)
    image_latents = pipe.get_image_latents(tensor, sample=False)
    reversed_latents = pipe.naive_forward_diffusion(image_latents, prompt="", num_inference_steps=inversion_steps, guidance_scale=1.0)
    return state.score(reversed_latents)


def run_adapter(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """执行 Gaussian Shading SD3.5 适配流程。"""

    import torch
    from PIL import Image

    prompt_rows = load_prompt_rows(Path(args.prompt_plan))
    if args.max_samples is not None:
        prompt_rows = prompt_rows[: int(args.max_samples)]
    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    if args.require_cuda and device != "cuda":
        raise RuntimeError("Gaussian Shading SD3.5 baseline 正式运行需要 CUDA GPU。")
    pipe = load_sd3_pipeline(model_id=args.model_id, device=device, torch_dtype_name=args.torch_dtype)

    artifact_root = Path(args.artifact_root) if args.artifact_root else Path(args.out).resolve().parent
    clean_dir = artifact_root / "images" / "clean"
    watermarked_dir = artifact_root / "images" / "watermarked"
    clean_dir.mkdir(parents=True, exist_ok=True)
    watermarked_dir.mkdir(parents=True, exist_ok=True)

    latent_shape = (1, int(args.latent_channels), int(args.height) // 8, int(args.width) // 8)
    image_pairs: list[dict[str, Any]] = []
    observations_without_threshold: list[dict[str, Any]] = []
    states: dict[str, GaussianShadingState] = {}

    for index, row in enumerate(prompt_rows, start=1):
        prompt = as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        prompt_id = row_id(row, index, "prompt_id", "prompt")
        image_id = row_id(row, index, "image_id", "gaussian_shading_image")
        file_stem = safe_file_stem(image_id, f"gaussian_shading_image_{index:04d}")
        generator = torch.Generator(device=device).manual_seed(int(args.seed) + index - 1)
        state = GaussianShadingState(
            shape=latent_shape,
            channel_copy=int(args.channel_copy),
            hw_copy=int(args.hw_copy),
            device=device,
            generator=generator,
        )
        states[image_id] = state
        clean_latents = torch.randn(latent_shape, generator=generator, device=device, dtype=pipe.transformer.dtype)
        watermarked_latents = state.create_watermarked_latents(generator=generator, dtype=pipe.transformer.dtype)

        clean_image = pipe(prompt, guidance_scale=float(args.guidance_scale), num_inference_steps=int(args.num_inference_steps), height=int(args.height), width=int(args.width), latents=clean_latents).images[0]
        watermarked_image = pipe(prompt, guidance_scale=float(args.guidance_scale), num_inference_steps=int(args.num_inference_steps), height=int(args.height), width=int(args.width), latents=watermarked_latents).images[0]
        clean_path = clean_dir / f"{file_stem}_clean.png"
        watermarked_path = watermarked_dir / f"{file_stem}_gaussian_shading.png"
        clean_image.save(clean_path)
        watermarked_image.save(watermarked_path)

        clean_score = _score_image(pipe, clean_image, state=state, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
        watermarked_score = _score_image(pipe, watermarked_image, state=state, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
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
            state = states.get(source_id)
            source_pair = next((item for item in image_pairs if item["image_id"] == source_id), None)
            if state is None or source_pair is None:
                continue
            with Image.open(Path(as_text(record.get("attacked_image_path")))) as attacked_image:
                score = _score_image(pipe, attacked_image, state=state, size=int(args.height), device=device, inversion_steps=int(args.num_inversion_steps))
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

    write_json(artifact_root / "image_pairs_gaussian_shading.json", image_pairs)
    manifest = {
        "artifact_name": "gaussian_shading_sd35_ceg_adapter_manifest.json",
        "producer_id": PRODUCER_ID,
        "baseline_id": BASELINE_ID,
        "model_id": args.model_id,
        "prompt_plan_path": str(Path(args.prompt_plan)),
        "artifact_root": str(artifact_root),
        "image_pair_count": len(image_pairs),
        "observation_count": len(observations),
        "latent_shape": list(latent_shape),
        "watermark_parameters": {"channel_copy": int(args.channel_copy), "hw_copy": int(args.hw_copy), "fpr": float(args.fpr)},
        "threshold": threshold,
        "threshold_source": threshold_source,
        "attacked_image_manifest_path": attacked_manifest_path,
        "formal_result_claim": False,
        "adapter_digest": build_stable_digest({"baseline_id": BASELINE_ID, "prompt_count": len(prompt_rows), "observation_count": len(observations)}),
    }
    return observations, manifest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 Gaussian Shading SD3.5 CEG baseline adapter。")
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
    parser.add_argument("--channel-copy", type=int, default=1)
    parser.add_argument("--hw-copy", type=int, default=8)
    parser.add_argument("--fpr", type=float, default=0.01)
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
    write_json(output_path.with_name("gaussian_shading_sd35_ceg_adapter_manifest.json"), manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
