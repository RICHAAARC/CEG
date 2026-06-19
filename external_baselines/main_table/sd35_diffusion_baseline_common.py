"""SD3.5 外部扩散水印 baseline 适配公共工具。

该文件位于 `external_baselines/`, 只服务 Tree-Ring、Gaussian Shading、Shallow Diffuse
等外部对比方法的实验适配。它不属于 CEG 主方法层, 不应被 `main/methods/ceg/` 反向依赖。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_json(path: str | Path) -> Any:
    """读取 JSON 文件, 使用 utf-8-sig 兼容 Windows 或 Colab 产生的 BOM。"""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Any) -> None:
    """写出 UTF-8 JSON 文件, 供后续论文流程读取。"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_text(value: Any, default: str = "") -> str:
    """把可选字段规范化为去空白字符串。"""

    if value is None:
        return default
    text = str(value).strip()
    return text or default


def load_prompt_rows(path: Path) -> list[dict[str, Any]]:
    """读取 CEG prompt plan, 支持 list 或包含 prompts/items/records/prompt_rows 的 object。"""

    payload = load_json(path)
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
        prompt_text = as_text(row.get("prompt_text") or row.get("prompt") or row.get("text"))
        if not prompt_text:
            raise ValueError(f"prompt plan 第 {index} 行缺少 prompt_text/prompt/text。")
        normalized.append(dict(row))
    if not normalized:
        raise ValueError("prompt plan 不能为空。")
    return normalized


def safe_file_stem(value: str, fallback: str) -> str:
    """把 image_id 转为安全文件名主干。"""

    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value).strip("._")
    return candidate or fallback


def row_id(row: dict[str, Any], index: int, field_name: str, fallback_prefix: str) -> str:
    """读取 prompt_id/image_id, 缺失时使用稳定序号。"""

    return as_text(row.get(field_name), f"{fallback_prefix}_{index:04d}")


def split_name(row: dict[str, Any]) -> str:
    """读取 split, 缺失时默认归入 test。"""

    return as_text(row.get("split"), "test")


def image_to_tensor(image: Any, *, size: int, device: str, dtype: Any):
    """把 PIL 图像转换为 SD VAE 输入张量, 范围为 [-1, 1]。"""

    import numpy as np
    import torch
    from PIL import Image

    resized = image.convert("RGB").resize((size, size), Image.Resampling.BICUBIC)
    array = np.asarray(resized).astype("float32") / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
    tensor = tensor * 2.0 - 1.0
    return tensor.to(device=device, dtype=dtype)


class InversionStableDiffusion3PipelineMixin:
    """为 StableDiffusion3Pipeline 增加轻量反演方法。"""

    def get_image_latents(self, image: Any, *, sample: bool = False):
        """通过 VAE 编码图像得到 latent。"""

        import torch

        with torch.inference_mode():
            encoding_dist = self.vae.encode(image).latent_dist
            encoding = encoding_dist.sample() if sample else encoding_dist.mode()
            shift_factor = float(getattr(self.vae.config, "shift_factor", 0.0) or 0.0)
            scaling_factor = float(getattr(self.vae.config, "scaling_factor", 1.0) or 1.0)
            return (encoding - shift_factor) * scaling_factor

    def naive_forward_diffusion(self, latents: Any, *, prompt: str = "", num_inference_steps: int = 5, guidance_scale: float = 1.0):
        """使用 SD3 scheduler 近似执行反向扩散的逆过程。"""

        import torch

        # 该函数用于检测反演, 不参与训练。必须显式关闭 autograd, 否则每个 transformer
        # 调用都会保留计算图, 在 22GB Colab GPU 上很容易因反演步数累积而 OOM。
        with torch.inference_mode():
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
                del noise_pred, latent_model_input, timestep_tensor
            return latents


def load_sd3_pipeline(*, model_id: str, device: str, torch_dtype_name: str):
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
    pipeline_class = type("ExternalBaselineInversionStableDiffusion3Pipeline", (InversionStableDiffusion3PipelineMixin, StableDiffusion3Pipeline), {})
    pipe = pipeline_class.from_pretrained(model_id, torch_dtype=torch_dtype)
    pipe = pipe.to(device)
    pipe.transformer.eval()
    pipe.vae.eval()
    pipe.set_progress_bar_config(disable=True)
    return pipe


def build_observation(
    *,
    baseline_id: str,
    score_name: str,
    producer_id: str,
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
        "baseline_id": baseline_id,
        "score": float(score),
        "threshold": float(threshold),
        "score_name": score_name,
        "higher_is_positive": True,
        "split": split_name(row),
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "prompt_id": row_id(row, index, "prompt_id", "prompt"),
        "image_id": image_id,
        "producer_id": producer_id,
        "producer_role": "external_baseline_sd35_adapter",
        "formal_result_claim": False,
        "threshold_source": threshold_source,
    }


def derive_threshold(observations: Iterable[dict[str, Any]], explicit_threshold: float | None) -> tuple[float, str]:
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
