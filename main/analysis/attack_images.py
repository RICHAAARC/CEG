"""执行轻量图像攻击并生成攻击 provenance manifest。

该模块属于实验产物准备层, 目标是把“攻击后图像如何产生”变成可复核文件。
它不会调用水印检测器, 不会修改 CEG 判定算法, 也不会声称 dry-run 攻击等价于正式论文攻击。
在其他项目中可复用的部分是: 以 image_pairs 为输入, 对每个 watermarked 图像执行攻击,
再输出 attacked_image_manifest、attack_shard_manifest 和可继续进入后续流程的 image_pairs。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest

ATTACKED_IMAGE_MANIFEST_NAME = "attacked_image_manifest.json"
ATTACK_SHARD_MANIFEST_NAME = "attack_shard_manifest.json"


def _optional_string(row: dict[str, Any], field_name: str) -> str | None:
    """读取可选字符串字段, 空字符串视为缺失。"""
    value = row.get(field_name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_watermarked_path(row: dict[str, Any]) -> Path:
    """从 image pair 行中读取水印图像路径。"""
    value = _optional_string(row, "watermarked_image_path") or _optional_string(row, "watermarked_path")
    if value is None:
        raise ValueError("image pair row missing watermarked image path")
    return Path(value)


def _source_clean_path(row: dict[str, Any]) -> Path:
    """从 image pair 行中读取 clean 图像路径, 用于生成 attacked-negative 评估样本。"""
    value = _optional_string(row, "clean_image_path") or _optional_string(row, "reference_path")
    if value is None:
        raise ValueError("image pair row missing clean image path")
    return Path(value)


def _image_id(row: dict[str, Any], index: int) -> str:
    """读取图像 ID, 缺失时使用稳定序号。"""
    return _optional_string(row, "image_id") or _optional_string(row, "event_id") or f"image_{index:04d}"


def _load_ppm_text(path: Path) -> tuple[str, int, int, int, list[int]]:
    """读取 ASCII PPM 图像, 用于无 Pillow 环境下的轻量攻击。"""
    tokens = []
    for line in path.read_text(encoding="ascii").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            tokens.extend(line.split())
    if len(tokens) < 4 or tokens[0] != "P3":
        raise ValueError(f"unsupported fallback image format: {path}")
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    pixels = [int(value) for value in tokens[4:]]
    if len(pixels) != width * height * 3:
        raise ValueError(f"PPM pixel count mismatch: {path}")
    return tokens[0], width, height, max_value, pixels


def _write_ppm(path: Path, width: int, height: int, max_value: int, pixels: list[int]) -> None:
    """写出 ASCII PPM 图像。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = " ".join(str(max(0, min(max_value, int(value)))) for value in pixels)
    path.write_text(f"P3\n{width} {height}\n{max_value}\n{body}\n", encoding="ascii")


def _apply_ppm_fallback_attack(source_path: Path, target_path: Path, attack_family: str) -> None:
    """在无 Pillow 环境下执行可复现的 PPM 轻量攻击。"""
    _, width, height, max_value, pixels = _load_ppm_text(source_path)
    if attack_family in {"identity", "copy"}:
        transformed = pixels
    elif attack_family in {"brightness_contrast", "brightness"}:
        transformed = [value + 8 for value in pixels]
    elif attack_family in {"gaussian_noise", "noise"}:
        transformed = [value + ((index % 3) - 1) * 5 for index, value in enumerate(pixels)]
    else:
        transformed = pixels
    _write_ppm(target_path, width, height, max_value, transformed)


def apply_attack_to_image(source_path: str | Path, target_path: str | Path, attack_family: str) -> dict[str, Any]:
    """对单张图像执行轻量攻击。

    通用工程写法: 优先使用 Pillow 处理常见图像格式, 无 Pillow 时退回到 PPM。
    项目特定写法: 攻击参数固定为轻量可复现值, 只用于建立正式 attack workflow 的文件契约。
    """
    source = Path(source_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageEnhance, ImageFilter  # type: ignore
    except ImportError:
        _apply_ppm_fallback_attack(source, target, attack_family)
        return {"backend": "ppm_fallback", "attack_family": attack_family}

    with Image.open(source) as image:
        rgb = image.convert("RGB")
        if attack_family == "jpeg":
            target = target.with_suffix(".jpg")
            rgb.save(target, format="JPEG", quality=75)
            return {"backend": "pillow", "attack_family": attack_family, "jpeg_quality": 75, "actual_target_path": str(target)}
        if attack_family == "resize":
            resized = rgb.resize((max(1, rgb.width // 2), max(1, rgb.height // 2))).resize((rgb.width, rgb.height))
            resized.save(target)
        elif attack_family == "rotate":
            rgb.rotate(3, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0)).save(target)
        elif attack_family == "gaussian_blur":
            rgb.filter(ImageFilter.GaussianBlur(radius=1.0)).save(target)
        elif attack_family == "brightness_contrast":
            bright = ImageEnhance.Brightness(rgb).enhance(1.08)
            ImageEnhance.Contrast(bright).enhance(1.05).save(target)
        else:
            shutil.copy2(source, target)
    return {"backend": "pillow", "attack_family": attack_family, "actual_target_path": str(target)}


def run_attack_workflow(
    image_pair_rows: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    attack_families: Iterable[str],
) -> dict[str, Any]:
    """执行攻击 workflow 并写出 manifest 与 attacked image pairs。"""
    output_path = Path(output_root)
    image_root = output_path / "attacked_images"
    manifest_root = output_path / "image_manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    rows = [dict(row) for row in image_pair_rows]
    attack_names = [str(item) for item in attack_families]
    attacked_records: list[dict[str, Any]] = []
    attacked_pairs: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        clean_path = _source_clean_path(row)
        watermarked_path = _source_watermarked_path(row)
        image_id = _image_id(row, index)
        for attack_family in attack_names:
            variants = [
                {
                    "source_path": watermarked_path,
                    "attacked_image_id": f"{image_id}_{attack_family}",
                    "sample_role": "attacked_positive",
                    "is_watermarked": True,
                    "source_variant": "watermarked",
                },
                {
                    "source_path": clean_path,
                    "attacked_image_id": f"{image_id}__clean_negative_{attack_family}",
                    "sample_role": "attacked_negative",
                    "is_watermarked": False,
                    "source_variant": "clean",
                },
            ]
            for variant in variants:
                source_path = Path(variant["source_path"])
                attacked_image_id = str(variant["attacked_image_id"])
                target_path = image_root / attack_family / f"{attacked_image_id}{source_path.suffix or '.ppm'}"
                attack_info = apply_attack_to_image(source_path, target_path, attack_family)
                actual_target = Path(str(attack_info.get("actual_target_path") or target_path))
                record = {
                    "attacked_image_id": attacked_image_id,
                    "source_image_id": image_id,
                    "event_id": _optional_string(row, "event_id"),
                    "sample_role": variant["sample_role"],
                    "is_watermarked": variant["is_watermarked"],
                    "source_variant": variant["source_variant"],
                    "clean_image_path": str(clean_path),
                    "watermarked_image_path": str(watermarked_path),
                    "source_image_path": str(source_path),
                    "attacked_image_path": str(actual_target),
                    "attack_family": attack_family,
                    "attack_condition": f"{attack_family}_default",
                    "attack_backend": attack_info["backend"],
                    "attack_parameters": {
                        key: value
                        for key, value in attack_info.items()
                        if key not in {"backend", "actual_target_path"}
                    },
                }
                attacked_records.append(record)
                attacked_pair = dict(row)
                attacked_pair["image_id"] = attacked_image_id
                attacked_pair["sample_role"] = variant["sample_role"]
                attacked_pair["is_watermarked"] = variant["is_watermarked"]
                attacked_pair["source_variant"] = variant["source_variant"]
                attacked_pair["attack_family"] = attack_family
                attacked_pair["attack_condition"] = f"{attack_family}_default"
                attacked_pair["attacked_image_path"] = str(actual_target)
                attacked_pair["attacked_path"] = str(actual_target)
                attacked_pairs.append(attacked_pair)
    attacked_manifest = {
        "artifact_name": ATTACKED_IMAGE_MANIFEST_NAME,
        "manifest_role": "attacked_image_provenance",
        "attacked_image_count": len(attacked_records),
        "attack_families": attack_names,
        "attacked_images": attacked_records,
        "manifest_digest": build_stable_digest(attacked_records),
    }
    shard_manifest = {
        "artifact_name": ATTACK_SHARD_MANIFEST_NAME,
        "manifest_role": "attack_shard_execution",
        "input_image_pair_count": len(rows),
        "attack_families": attack_names,
        "attacked_image_manifest_path": f"image_manifests/{ATTACKED_IMAGE_MANIFEST_NAME}",
        "attacked_image_pairs_path": "image_pairs_attacked.json",
        "shard_digest": build_stable_digest({"rows": rows, "attacks": attack_names, "attacked_records": attacked_records}),
    }
    (manifest_root / ATTACKED_IMAGE_MANIFEST_NAME).write_text(
        json.dumps(attacked_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (manifest_root / ATTACK_SHARD_MANIFEST_NAME).write_text(
        json.dumps(shard_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / "image_pairs_attacked.json").write_text(
        json.dumps(attacked_pairs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return shard_manifest
