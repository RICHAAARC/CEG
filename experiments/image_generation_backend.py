"""从 prompt plan 生成轻量 mock 图像和图像 provenance manifest。

该模块属于实验输入准备层, 作用是把论文图像实验的起点从“已有 image_pairs”前移到
“prompt plan”。它只实现 CPU 可运行的 mock backend, 不调用真实 SD 模型, 不声称生成图像
具有正式论文质量。在其他项目中可复用的部分是: 用稳定 prompt / seed / model 配置生成
可追溯 image_pairs 和 image manifests, 供 attack、detection、quality metric 和结果包流程消费。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from main.analysis.image_examples import build_image_generation_manifest, build_image_pair_manifest
from main.core.digest import build_stable_digest

MOCK_IMAGE_GENERATION_BACKEND_MANIFEST_NAME = "mock_image_generation_backend_manifest.json"
PROMPT_PLAN_NAME = "prompt_plan.json"
IMAGE_PAIRS_NAME = "image_pairs.json"


def _optional_string(row: dict[str, Any], field_name: str, default: str = "") -> str:
    """读取字符串字段, 缺失时返回显式默认值。"""
    value = row.get(field_name)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _stable_color(seed: int, channel_offset: int) -> int:
    """根据 seed 生成稳定 PPM 颜色通道, 使 mock 图像可复现。"""
    return 20 + ((seed * 37 + channel_offset * 53) % 180)


def _write_ppm(path: Path, red: int, green: int, blue: int) -> None:
    """写出 1x1 ASCII PPM 图像, 作为无 GPU dry-run 的最小图像文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"P3\n1 1\n255\n{red} {green} {blue}\n", encoding="ascii")


def build_prompt_plan_from_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """从 dry-run 或 sample events 派生 prompt plan。

    通用工程写法是让上游 prompt plan 与下游 event_id 建立稳定映射。项目特定部分在于
    dry-run prompt 使用固定文本, 只用于验证论文流程的文件契约和 provenance, 不作为正式图像生成。
    """
    prompt_rows: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        event_id = _optional_string(event, "event_id", f"event_{index:04d}")
        prompt_rows.append(
            {
                "prompt_id": f"dry_run_prompt_{index:03d}",
                "prompt_text": "dry-run synthetic prompt for pipeline validation",
                "event_id": event_id,
                "image_id": event_id,
                "seed": index,
                "model_id": "mock_ppm_image_generation_backend",
                "scheduler": "not_applicable",
                "num_inference_steps": 0,
                "guidance_scale": 0.0,
                "method_name": "ceg",
                "split": _optional_string(event, "split", "test"),
                "sample_role": _optional_string(event, "sample_role", "unknown_role"),
                "attack_family": _optional_string(event, "attack_family", "clean"),
                "attack_condition": _optional_string(event, "attack_condition", "clean_none"),
            }
        )
    return prompt_rows


def _image_pair_from_prompt(row: dict[str, Any], output_root: Path, index: int) -> dict[str, Any]:
    """根据单条 prompt row 写出 clean / watermarked mock 图像并返回 image pair 行。"""
    image_id = _optional_string(row, "image_id", _optional_string(row, "event_id", f"image_{index:04d}"))
    seed = int(row.get("seed", index))
    clean_path = output_root / "images" / "clean" / f"{image_id}.ppm"
    watermarked_path = output_root / "images" / "watermarked" / f"{image_id}.ppm"
    attacked_path = output_root / "images" / "attacked" / f"{image_id}.ppm"
    red = _stable_color(seed, 1)
    green = _stable_color(seed, 2)
    blue = _stable_color(seed, 3)
    _write_ppm(clean_path, red, green, blue)
    _write_ppm(watermarked_path, min(255, red + 2), max(0, green - 1), blue)
    _write_ppm(attacked_path, min(255, red + 3), max(0, green - 2), max(0, blue - 1))
    return {
        "image_id": image_id,
        "event_id": _optional_string(row, "event_id", image_id),
        "prompt_id": _optional_string(row, "prompt_id", f"prompt_{index:04d}"),
        "prompt_text": _optional_string(row, "prompt_text", "mock prompt"),
        "seed": seed,
        "model_id": _optional_string(row, "model_id", "mock_ppm_image_generation_backend"),
        "scheduler": _optional_string(row, "scheduler", "not_applicable"),
        "num_inference_steps": int(row.get("num_inference_steps", 0)),
        "guidance_scale": float(row.get("guidance_scale", 0.0)),
        "method_name": _optional_string(row, "method_name", "ceg"),
        "split": _optional_string(row, "split", "test"),
        "sample_role": _optional_string(row, "sample_role", "unknown_role"),
        "attack_family": _optional_string(row, "attack_family", "clean"),
        "attack_condition": _optional_string(row, "attack_condition", "clean_none"),
        "clean_image_path": str(clean_path),
        "watermarked_image_path": str(watermarked_path),
        "attacked_image_path": str(attacked_path),
        "reference_path": str(clean_path),
        "watermarked_path": str(watermarked_path),
        "mock_backend_id": "mock_ppm_image_generation_backend",
    }


def write_mock_image_generation_from_prompt_plan(
    prompt_rows: Iterable[dict[str, Any]],
    output_root: str | Path,
) -> dict[str, Any]:
    """写出 mock 图像、image_pairs 和 image manifests。

    输出文件可以被 `scripts/run_image_attack_workflow.py`、`scripts/build_paper_outputs.py` 和
    Colab dry-run 继续消费。正式实验可复用同一 manifest 契约, 但应替换为 external backend。
    """
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    rows = [dict(row) for row in prompt_rows]
    image_pairs = [_image_pair_from_prompt(row, output_path, index) for index, row in enumerate(rows, start=1)]
    manifest_root = output_path / "image_manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    (output_path / PROMPT_PLAN_NAME).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_path / IMAGE_PAIRS_NAME).write_text(
        json.dumps(image_pairs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    generation_manifest = build_image_generation_manifest(image_pairs)
    pair_manifest = build_image_pair_manifest(image_pairs)
    (manifest_root / "image_generation_manifest.json").write_text(
        json.dumps(generation_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (manifest_root / "image_pair_manifest.json").write_text(
        json.dumps(pair_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    backend_manifest = {
        "artifact_name": MOCK_IMAGE_GENERATION_BACKEND_MANIFEST_NAME,
        "backend_id": "mock_ppm_image_generation_backend",
        "backend_role": "mock_backend",
        "prompt_plan_path": PROMPT_PLAN_NAME,
        "image_pairs_path": IMAGE_PAIRS_NAME,
        "image_generation_manifest_path": "image_manifests/image_generation_manifest.json",
        "image_pair_manifest_path": "image_manifests/image_pair_manifest.json",
        "prompt_count": len(rows),
        "image_pair_count": len(image_pairs),
        "image_format": "ppm_ascii_1x1",
        "formal_result_claim": False,
        "records_digest": build_stable_digest({"prompt_rows": rows, "image_pairs": image_pairs}),
    }
    (output_path / MOCK_IMAGE_GENERATION_BACKEND_MANIFEST_NAME).write_text(
        json.dumps(backend_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backend_manifest
