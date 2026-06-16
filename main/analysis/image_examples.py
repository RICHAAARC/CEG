"""导出论文结果包中的图像 manifest 和示例图。

该模块属于论文产物治理层, 它只复制和索引已经存在的图像文件。
它不会生成图像, 不会调用 SD 模型, 也不会把 dry-run 图像伪装成正式结果。
在其他项目中可复用的部分是: 用统一 image pair rows 描述图像来源,
再由可审计 manifest 记录示例图的来源、角色、摘要和结果包相对路径。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest

IMAGE_GENERATION_MANIFEST_NAME = "image_generation_manifest.json"
IMAGE_PAIR_MANIFEST_NAME = "image_pair_manifest.json"
IMAGE_EXAMPLE_MANIFEST_NAME = "image_example_manifest.json"


def _file_sha256(path: Path) -> str:
    """计算图像文件摘要, 用于结果包离线复核。"""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_string(row: dict[str, Any], field_name: str) -> str | None:
    """读取可选字符串字段, 空字符串视为缺失。"""
    value = row.get(field_name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _image_id(row: dict[str, Any], index: int) -> str:
    """读取图像 ID, 缺失时使用稳定序号生成审计友好的 ID。"""
    return _optional_string(row, "image_id") or _optional_string(row, "event_id") or f"image_{index:04d}"


def _copy_example(
    source_path: Path,
    output_root: Path,
    *,
    role: str,
    image_id: str,
    example_index: int,
) -> dict[str, Any]:
    """复制单张示例图并返回 manifest 条目。"""
    if not source_path.is_file():
        raise FileNotFoundError(f"image example source missing: {source_path}")
    suffix = source_path.suffix or ".img"
    relative_path = Path("image_examples") / role / f"{example_index:04d}_{image_id}{suffix}"
    target_path = output_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return {
        "example_id": f"{role}_{example_index:04d}_{image_id}",
        "example_role": role,
        "image_id": image_id,
        "source_path": str(source_path),
        "relative_path": str(relative_path).replace("\\", "/"),
        "byte_count": target_path.stat().st_size,
        "sha256": _file_sha256(target_path),
    }


def build_image_generation_manifest(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """从 image pair rows 中提取生成配置和 prompt provenance。

    如果真实后端提供了 prompt、seed、model_id 等字段, 这些字段会进入 manifest。
    如果输入只包含图像路径, manifest 会显式保留较少字段, 不补造未知生成配置。
    """
    materialized = [dict(row) for row in rows]
    generation_fields = (
        "image_id",
        "prompt_id",
        "prompt_text",
        "seed",
        "model_id",
        "scheduler",
        "num_inference_steps",
        "guidance_scale",
        "split",
        "sample_role",
        "method_name",
    )
    records = [
        {field: row[field] for field in generation_fields if field in row and row[field] not in {None, ""}}
        for row in materialized
    ]
    return {
        "artifact_name": IMAGE_GENERATION_MANIFEST_NAME,
        "manifest_role": "image_generation_provenance",
        "record_count": len(records),
        "generation_records": records,
        "manifest_digest": build_stable_digest(records),
    }


def build_image_pair_manifest(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """构建 clean / watermarked / attacked 图像配对 manifest。"""
    materialized = [dict(row) for row in rows]
    pair_records: list[dict[str, Any]] = []
    for index, row in enumerate(materialized, start=1):
        pair_records.append(
            {
                "image_id": _image_id(row, index),
                "event_id": _optional_string(row, "event_id"),
                "prompt_id": _optional_string(row, "prompt_id"),
                "split": _optional_string(row, "split"),
                "sample_role": _optional_string(row, "sample_role"),
                "attack_family": _optional_string(row, "attack_family"),
                "attack_condition": _optional_string(row, "attack_condition"),
                "method_name": _optional_string(row, "method_name") or "ceg",
                "clean_image_path": _optional_string(row, "clean_image_path") or _optional_string(row, "reference_path"),
                "watermarked_image_path": _optional_string(row, "watermarked_image_path")
                or _optional_string(row, "watermarked_path"),
                "attacked_image_path": _optional_string(row, "attacked_image_path") or _optional_string(row, "attacked_path"),
            }
        )
    return {
        "artifact_name": IMAGE_PAIR_MANIFEST_NAME,
        "manifest_role": "image_pair_provenance",
        "image_pair_count": len(pair_records),
        "image_pairs": pair_records,
        "manifest_digest": build_stable_digest(pair_records),
    }


def export_image_example_package(
    rows: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    max_examples_per_role: int = 8,
) -> dict[str, Any]:
    """复制论文示例图并写出 image manifests。

    rows 通常来自 `image_pairs.json`。每行可以包含 `reference_path` / `clean_image_path`,
    `watermarked_path` / `watermarked_image_path`, 以及可选的 attacked 图像路径。
    """
    if max_examples_per_role < 1:
        raise ValueError("max_examples_per_role must be >= 1")
    output_path = Path(output_root)
    manifest_root = output_path / "image_manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    rows_list = [dict(row) for row in rows]
    (manifest_root / IMAGE_GENERATION_MANIFEST_NAME).write_text(
        json.dumps(build_image_generation_manifest(rows_list), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pair_manifest = build_image_pair_manifest(rows_list)
    (manifest_root / IMAGE_PAIR_MANIFEST_NAME).write_text(
        json.dumps(pair_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    examples: list[dict[str, Any]] = []
    role_counts = {"clean": 0, "watermarked": 0, "attacked": 0}
    for index, row in enumerate(rows_list, start=1):
        image_id = _image_id(row, index)
        candidates = {
            "clean": _optional_string(row, "clean_image_path") or _optional_string(row, "reference_path"),
            "watermarked": _optional_string(row, "watermarked_image_path") or _optional_string(row, "watermarked_path"),
            "attacked": _optional_string(row, "attacked_image_path") or _optional_string(row, "attacked_path"),
        }
        for role, source in candidates.items():
            if not source or role_counts[role] >= max_examples_per_role:
                continue
            role_counts[role] += 1
            entry = _copy_example(Path(source), output_path, role=role, image_id=image_id, example_index=role_counts[role])
            for field in ("event_id", "prompt_id", "method_name", "attack_family", "attack_condition", "split", "sample_role"):
                value = _optional_string(row, field)
                if value is not None:
                    entry[field] = value
            examples.append(entry)

    manifest = {
        "artifact_name": IMAGE_EXAMPLE_MANIFEST_NAME,
        "manifest_role": "paper_image_examples",
        "example_count": len(examples),
        "role_counts": role_counts,
        "examples": examples,
        "source_image_pair_manifest": f"image_manifests/{IMAGE_PAIR_MANIFEST_NAME}",
        "manifest_digest": build_stable_digest(examples),
    }
    example_manifest_path = output_path / "image_examples" / IMAGE_EXAMPLE_MANIFEST_NAME
    example_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    example_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
