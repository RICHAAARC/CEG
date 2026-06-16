"""从图像 provenance 生成轻量 CEG detection 协议事件。

该模块把 `image_pairs.json` 和 `attacked_image_manifest.json` 转换为 CEG 论文协议事件。
它不运行真实水印检测模型, 不读取 SD 模型, 也不声称输出分数具有论文结论意义。它的作用是
建立正式 detection backend 需要遵守的 records 契约: 图像样本、攻击 provenance、检测分数、
attestation 和几何诊断必须最终进入统一 event records。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest
from main.methods.ceg.ablations import CEG_ABLATIONS

DETECTION_EVENTS_NAME = "detection_events.json"
DETECTION_THRESHOLDS_NAME = "detection_thresholds.json"
DETECTION_PRODUCER_MANIFEST_NAME = "ceg_detection_producer_manifest.json"


def _optional_string(row: dict[str, Any], field_name: str, default: str | None = None) -> str | None:
    """读取可选字符串字段, 空字符串按缺失处理。"""
    value = row.get(field_name)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _bool_from_any(value: Any, *, default: bool) -> bool:
    """读取布尔字段, 支持常见字符串表示。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y", "watermarked", "positive"}:
        return True
    if lowered in {"false", "0", "no", "n", "clean", "negative"}:
        return False
    return default


def _infer_is_watermarked(row: dict[str, Any]) -> bool:
    """从 image pair 行中推断样本是否为水印正样本。"""
    if "is_watermarked" in row:
        return _bool_from_any(row.get("is_watermarked"), default=False)
    role = (_optional_string(row, "sample_role", "") or "").lower()
    if "negative" in role:
        return False
    if "positive" in role or "watermarked" in role:
        return True
    return True


def _image_id(row: dict[str, Any], index: int) -> str:
    """读取稳定图像标识。"""
    return _optional_string(row, "image_id") or _optional_string(row, "event_id") or f"image_{index:04d}"


def _stable_small_offset(text: str) -> float:
    """根据字符串生成小幅稳定偏移, 让 dry-run 分数可复现但不完全相同。"""
    return (sum(ord(char) for char in text) % 17) / 1000.0


def _score_payload(*, image_id: str, is_watermarked: bool, attacked: bool) -> dict[str, Any]:
    """生成轻量检测 payload。

    通用工程价值在于输出结构与真实 detector 相同。项目特定部分在于分数是 deterministic dry-run
    规则, 只用于验证事件、表格、TPR@FPR 和结果包重建链路。
    """
    offset = _stable_small_offset(image_id)
    if is_watermarked and attacked:
        content_score_raw = 0.48 + offset
        content_score_aligned = 0.63 + offset
        content_fail_reason = "geometry_suspected"
        attestation_score = 0.91
        geometry = {
            "registration_confidence": 0.88,
            "anchor_inlier_ratio": 0.83,
            "recovered_sync_consistency": 0.86,
            "alignment_residual": 0.09,
        }
    elif is_watermarked:
        content_score_raw = 0.72 + offset
        content_score_aligned = 0.75 + offset
        content_fail_reason = "high_confidence"
        attestation_score = 0.93
        geometry = {
            "registration_confidence": 0.9,
            "anchor_inlier_ratio": 0.85,
            "recovered_sync_consistency": 0.88,
            "alignment_residual": 0.08,
        }
    else:
        content_score_raw = 0.18 + offset
        content_score_aligned = 0.2 + offset
        content_fail_reason = "dry_run_negative"
        attestation_score = 0.16
        geometry = {
            "registration_confidence": 0.42,
            "anchor_inlier_ratio": 0.45,
            "recovered_sync_consistency": 0.44,
            "alignment_residual": 0.24,
            "geometry_fail_reason": "dry_run_negative_geometry",
        }
    return {
        "thresholds": {
            "content_threshold": 0.5,
            "attestation_threshold": 0.5,
            "registration_confidence_min": 0.3,
            "anchor_inlier_ratio_min": 0.5,
            "recovered_sync_consistency_min": 0.55,
            "rescue_delta_low": 0.05,
        },
        "content": {
            "content_score_raw": round(content_score_raw, 6),
            "content_score_aligned": round(content_score_aligned, 6),
            "content_fail_reason": content_fail_reason,
        },
        "geometry": geometry,
        "attestation": {"attestation_score": attestation_score},
        "ceg_ablation_variants": list(CEG_ABLATIONS),
        "detection_source": {
            "producer": "ceg_lightweight_detection_producer",
            "formal_result_claim": False,
        },
    }


def _event_from_image_pair(row: dict[str, Any], index: int) -> dict[str, Any]:
    """从 image pair 行生成 watermarked / clean 检测事件。"""
    image_id = _image_id(row, index)
    is_watermarked = _infer_is_watermarked(row)
    sample_role = _optional_string(row, "sample_role") or ("positive_source" if is_watermarked else "clean_negative")
    payload = _score_payload(image_id=image_id, is_watermarked=is_watermarked, attacked=False)
    payload["image_provenance"] = {
        "image_id": image_id,
        "prompt_id": _optional_string(row, "prompt_id"),
        "clean_image_path": _optional_string(row, "clean_image_path") or _optional_string(row, "reference_path"),
        "watermarked_image_path": _optional_string(row, "watermarked_image_path") or _optional_string(row, "watermarked_path"),
    }
    return {
        "event_id": _optional_string(row, "event_id", image_id),
        "method_name": "ceg",
        "split": _optional_string(row, "split", "test"),
        "sample_role": sample_role,
        "attack_family": _optional_string(row, "attack_family", "clean") or "clean",
        "attack_condition": _optional_string(row, "attack_condition", "clean_none") or "clean_none",
        "is_watermarked": is_watermarked,
        "payload": payload,
    }


def _source_lookup(image_pair_rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """构建 event_id 和 image_id 到 image pair 行的查找表。"""
    lookup: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(image_pair_rows, start=1):
        materialized = dict(row)
        for key in (_image_id(materialized, index), _optional_string(materialized, "event_id")):
            if key:
                lookup[str(key)] = materialized
    return lookup


def _event_from_attack_record(record: dict[str, Any], source_row: dict[str, Any] | None, index: int) -> dict[str, Any]:
    """从 attack manifest 记录生成 attacked detection 事件。"""
    attacked_image_id = _optional_string(record, "attacked_image_id", f"attacked_{index:04d}") or f"attacked_{index:04d}"
    source = source_row or {}
    is_watermarked = _infer_is_watermarked(source) if source else True
    payload = _score_payload(image_id=attacked_image_id, is_watermarked=is_watermarked, attacked=True)
    payload["image_provenance"] = {
        "image_id": attacked_image_id,
        "source_image_id": _optional_string(record, "source_image_id"),
        "watermarked_image_path": _optional_string(record, "watermarked_image_path"),
        "attacked_image_path": _optional_string(record, "attacked_image_path"),
    }
    return {
        "event_id": attacked_image_id,
        "method_name": "ceg",
        "split": _optional_string(source, "split", "test") or "test",
        "sample_role": "attacked_positive" if is_watermarked else "attacked_negative",
        "attack_family": _optional_string(record, "attack_family", "unknown_attack") or "unknown_attack",
        "attack_condition": _optional_string(record, "attack_condition", "unknown_attack_condition") or "unknown_attack_condition",
        "is_watermarked": is_watermarked,
        "payload": payload,
    }


def build_detection_events_from_image_manifests(
    image_pair_rows: Iterable[dict[str, Any]],
    attacked_image_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """从 image pairs 和可选 attacked image manifest 构建 CEG detection events。"""
    pairs = [dict(row) for row in image_pair_rows]
    events = [_event_from_image_pair(row, index) for index, row in enumerate(pairs, start=1)]
    if attacked_image_manifest:
        lookup = _source_lookup(pairs)
        attack_records = attacked_image_manifest.get("attacked_images", [])
        if not isinstance(attack_records, list):
            raise TypeError("attacked_image_manifest.attacked_images must be list")
        for index, record in enumerate(attack_records, start=1):
            if not isinstance(record, dict):
                raise TypeError(f"attacked_images[{index}] must be object")
            source_key = _optional_string(record, "source_image_id") or _optional_string(record, "event_id")
            source_row = lookup.get(source_key or "")
            events.append(_event_from_attack_record(record, source_row, index))
    return events


def default_detection_thresholds() -> dict[str, float]:
    """返回 detection producer dry-run 阈值映射。"""
    thresholds = {"ceg": 0.5}
    for variant in CEG_ABLATIONS:
        thresholds[f"ceg_{variant.lower().replace('-', '_')}"] = 0.5
    return thresholds


def write_detection_inputs_from_image_manifests(
    image_pair_rows: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    attacked_image_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写出 detection events、thresholds 和 producer manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    events = build_detection_events_from_image_manifests(image_pair_rows, attacked_image_manifest)
    thresholds = default_detection_thresholds()
    (output_path / DETECTION_EVENTS_NAME).write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / DETECTION_THRESHOLDS_NAME).write_text(
        json.dumps(thresholds, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "artifact_name": DETECTION_PRODUCER_MANIFEST_NAME,
        "producer_id": "ceg_lightweight_detection_producer",
        "producer_role": "detection_contract_dry_run",
        "formal_result_claim": False,
        "events_path": DETECTION_EVENTS_NAME,
        "thresholds_path": DETECTION_THRESHOLDS_NAME,
        "event_count": len(events),
        "attacked_manifest_consumed": attacked_image_manifest is not None,
        "sample_roles": sorted({str(event["sample_role"]) for event in events}),
        "attack_families": sorted({str(event["attack_family"]) for event in events}),
        "producer_digest": build_stable_digest({"events": events, "thresholds": thresholds}),
    }
    (output_path / DETECTION_PRODUCER_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
