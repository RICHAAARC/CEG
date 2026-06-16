"""把真实实验样本清单转换为 CEG 协议事件。

该模块面向 Colab 或集群冷启动流程。它不生成图像, 不运行第三方 baseline, 也不伪造 CEG 证据;
它只把上游检测器、几何恢复器、attestation 组件或人工整理的样本清单规范化为
`scripts/build_paper_outputs.py` 可消费的事件 JSON。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest
from main.methods.ceg.ablations import CEG_ABLATIONS

REQUIRED_SAMPLE_COLUMNS = (
    "event_id",
    "split",
    "sample_role",
    "attack_family",
    "attack_condition",
    "is_watermarked",
    "content_score_raw",
    "attestation_score",
)

GEOMETRY_COLUMNS = (
    "registration_confidence",
    "anchor_inlier_ratio",
    "recovered_sync_consistency",
    "alignment_residual",
    "geometry_fail_reason",
)

CONTENT_OPTIONAL_COLUMNS = (
    "content_score_aligned",
    "content_fail_reason",
    "payload_probe_score",
)

STANDARD_METRIC_COLUMNS = (
    "bit_correct_count",
    "bit_total_count",
    "bit_accuracy",
    "payload_recovered",
    "psnr",
    "ssim",
    "lpips",
    "fid",
    "clip_score",
)

IMAGE_PAIR_COLUMNS = (
    "image_id",
    "reference_path",
    "watermarked_path",
    "method_name",
)


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON 数组或 JSONL 样本清单。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("sample manifest JSON must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV 样本清单。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_sample_manifest(path: str | Path) -> list[dict[str, Any]]:
    """读取 JSON / JSONL / CSV 格式的真实实验样本清单。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported sample manifest extension: {input_path.suffix}")
    return [dict(row) for row in rows]


def load_threshold_map(path: str | Path) -> dict[str, float]:
    """读取 method_name 到 content_threshold 的阈值映射。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("threshold map must contain an object")
    return {str(key): float(value) for key, value in payload.items()}


def _is_missing(value: Any) -> bool:
    """判断清单字段是否为空。"""
    return value is None or (isinstance(value, str) and value.strip() == "")


def _as_float(row: dict[str, Any], field_name: str, *, required: bool = False) -> float | None:
    """读取浮点字段, 空值在非必填场景下返回 None。"""
    value = row.get(field_name)
    if _is_missing(value):
        if required:
            raise ValueError(f"sample row missing required numeric field: {field_name}")
        return None
    if isinstance(value, bool):
        raise TypeError(f"sample field must be numeric, not bool: {field_name}")
    return float(value)


def _as_bool(row: dict[str, Any], field_name: str, *, required: bool = False) -> bool | None:
    """读取布尔字段, 支持常见字符串表示。"""
    value = row.get(field_name)
    if _is_missing(value):
        if required:
            raise ValueError(f"sample row missing required boolean field: {field_name}")
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"sample field must be boolean-like: {field_name}")


def _required_string(row: dict[str, Any], field_name: str) -> str:
    """读取必填字符串字段。"""
    value = row.get(field_name)
    if _is_missing(value):
        raise ValueError(f"sample row missing required field: {field_name}")
    return str(value)


def _optional_string(row: dict[str, Any], field_name: str) -> str | None:
    """读取可选字符串字段。"""
    value = row.get(field_name)
    return None if _is_missing(value) else str(value)


def _threshold_payload(row: dict[str, Any], thresholds: dict[str, float]) -> dict[str, float]:
    """构造单事件阈值节点。

    content_threshold 优先使用样本行内字段, 其次使用 method_name 对应阈值, 最后使用 ceg 阈值。
    attestation 和几何阈值允许在样本行中覆盖, 否则使用稳定默认值。
    """
    method_name = str(row.get("method_name") or "ceg")
    content_threshold = _as_float(row, "content_threshold")
    if content_threshold is None:
        content_threshold = float(thresholds.get(method_name, thresholds.get("ceg", 0.5)))
    return {
        "content_threshold": content_threshold,
        "attestation_threshold": _as_float(row, "attestation_threshold") or 0.5,
        "registration_confidence_min": _as_float(row, "registration_confidence_min") or 0.3,
        "anchor_inlier_ratio_min": _as_float(row, "anchor_inlier_ratio_min") or 0.5,
        "recovered_sync_consistency_min": _as_float(row, "recovered_sync_consistency_min") or 0.55,
        "rescue_delta_low": _as_float(row, "rescue_delta_low") or 0.05,
    }


def _standard_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """从样本清单中提取可直接进入 records 的标准水印指标。"""
    output: dict[str, Any] = {}
    for field_name in STANDARD_METRIC_COLUMNS:
        if field_name == "payload_recovered":
            value = _as_bool(row, field_name)
        else:
            value = _as_float(row, field_name)
        if value is not None:
            output[field_name] = value
    return output


def _ceg_ablation_variants(row: dict[str, Any]) -> list[str]:
    """读取样本清单声明的消融版本, 缺省时使用项目完整消融集合。"""
    raw = row.get("ceg_ablation_variants")
    if _is_missing(raw):
        return list(CEG_ABLATIONS)
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def build_protocol_events_from_sample_rows(
    sample_rows: Iterable[dict[str, Any]],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    """把样本清单行转换为协议事件 JSON 行。"""
    events: list[dict[str, Any]] = []
    for index, raw_row in enumerate(sample_rows):
        row = dict(raw_row)
        missing = [field for field in REQUIRED_SAMPLE_COLUMNS if _is_missing(row.get(field))]
        if missing:
            raise ValueError(f"sample row {index} missing required columns: {missing}")
        content = {
            "content_score_raw": _as_float(row, "content_score_raw", required=True),
            "content_fail_reason": _optional_string(row, "content_fail_reason") or "sample_manifest_not_provided",
        }
        for field_name in ("content_score_aligned", "payload_probe_score"):
            value = _as_float(row, field_name)
            if value is not None:
                content[field_name] = value
        geometry: dict[str, Any] = {}
        for field_name in GEOMETRY_COLUMNS:
            if field_name == "geometry_fail_reason":
                value = _optional_string(row, field_name)
            else:
                value = _as_float(row, field_name)
            if value is not None:
                geometry[field_name] = value
        payload = {
            "thresholds": _threshold_payload(row, thresholds),
            "content": content,
            "geometry": geometry,
            "attestation": {"attestation_score": _as_float(row, "attestation_score", required=True)},
            "ceg_ablation_variants": _ceg_ablation_variants(row),
        }
        metrics = _standard_metrics(row)
        if metrics:
            payload["standard_metrics"] = metrics
        events.append(
            {
                "event_id": _required_string(row, "event_id"),
                "method_name": str(row.get("method_name") or "ceg"),
                "split": _required_string(row, "split"),
                "sample_role": _required_string(row, "sample_role"),
                "attack_family": _required_string(row, "attack_family"),
                "attack_condition": _required_string(row, "attack_condition"),
                "is_watermarked": bool(_as_bool(row, "is_watermarked", required=True)),
                "payload": payload,
            }
        )
    return events


def build_image_pair_rows(sample_rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """从样本清单中提取可供 compute_image_quality_metrics.py 消费的图像配对。"""
    pairs: list[dict[str, str]] = []
    for row in sample_rows:
        reference_path = _optional_string(row, "reference_path")
        watermarked_path = _optional_string(row, "watermarked_path")
        if not reference_path or not watermarked_path:
            continue
        pair: dict[str, str] = {
            "reference_path": reference_path,
            "watermarked_path": watermarked_path,
            "image_id": _optional_string(row, "image_id") or _required_string(row, "event_id"),
            "event_id": _required_string(row, "event_id"),
            "method_name": str(row.get("method_name") or "ceg"),
            "split": _required_string(row, "split"),
            "sample_role": _required_string(row, "sample_role"),
            "attack_family": _required_string(row, "attack_family"),
            "attack_condition": _required_string(row, "attack_condition"),
        }
        pairs.append(pair)
    return pairs


def write_protocol_event_inputs_from_sample_manifest(
    sample_manifest_path: str | Path,
    threshold_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """写出 events.json、image_pairs.json 和样本转换 manifest。"""
    rows = load_sample_manifest(sample_manifest_path)
    thresholds = load_threshold_map(threshold_path)
    events = build_protocol_events_from_sample_rows(rows, thresholds)
    image_pairs = build_image_pair_rows(rows)
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    events_path = output_path / "events.json"
    image_pairs_path = output_path / "image_pairs.json"
    manifest_path = output_path / "sample_event_build_manifest.json"
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    image_pairs_path.write_text(json.dumps(image_pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "artifact_name": "sample_event_build_manifest.json",
        "sample_manifest_path": str(Path(sample_manifest_path).resolve()),
        "threshold_path": str(Path(threshold_path).resolve()),
        "events_path": "events.json",
        "image_pairs_path": "image_pairs.json",
        "sample_row_count": len(rows),
        "event_count": len(events),
        "image_pair_count": len(image_pairs),
        "splits": sorted({str(event["split"]) for event in events}),
        "sample_roles": sorted({str(event["sample_role"]) for event in events}),
        "attack_families": sorted({str(event["attack_family"]) for event in events}),
    }
    manifest["sample_event_digest"] = build_stable_digest(
        {"events": events, "image_pairs": image_pairs, "thresholds": thresholds}
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
