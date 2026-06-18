"""读取和合并外部高级指标文件。

LPIPS、FID、CLIP score 等指标通常依赖专用模型、参考统计量或第三方工具。
本模块不伪造这些指标, 只定义它们进入 CEG 论文 records 的标准文件契约和合并规则。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest


STANDARD_METRIC_COLUMNS = {
    "bit_correct_count",
    "bit_total_count",
    "bit_accuracy",
    "payload_recovered",
    "psnr",
    "ssim",
    "lpips",
    "fid",
    "clip_score",
    "mse",
    "mae",
}

IDENTITY_COLUMNS = {"event_id", "method_name", "baseline_id"}
METRIC_ROW_IMPORT_MANIFEST_NAME = "metric_execution_manifest.json"


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON 数组或 JSONL 指标行。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("metric JSON file must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV 指标行。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _coerce_value(value: Any) -> Any:
    """把外部文件中的字符串值转换为 records 友好的标量。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    lowered = stripped.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    try:
        return float(stripped)
    except ValueError:
        return stripped


def load_metric_rows(path: str | Path) -> list[dict[str, Any]]:
    """从 JSON / JSONL / CSV 文件读取高级指标行。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported metric file extension: {input_path.suffix}")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if "event_id" not in row:
            raise ValueError(f"metric row missing event_id at index {index}")
        metric_values = {
            key: _coerce_value(value)
            for key, value in row.items()
            if key in STANDARD_METRIC_COLUMNS and _coerce_value(value) is not None
        }
        if not metric_values:
            raise ValueError(f"metric row has no supported metric columns at index {index}")
        normalized.append(
            {
                **{key: str(row[key]) for key in IDENTITY_COLUMNS if key in row and row[key] not in {None, ""}},
                **metric_values,
            }
        )
    return normalized


def build_metric_row_import_manifest(
    rows: Iterable[dict[str, Any]],
    *,
    source_metric_rows_path: str | Path,
    output_metric_rows_path: str | Path,
    formal_result_claim: bool = False,
    evidence_paths: Iterable[str | Path] = (),
    producer_id: str = "external_metric_row_importer",
) -> dict[str, Any]:
    """为离线高级指标 rows 文件生成可归档的执行 manifest.

    通用工程写法:
    - LPIPS、FID 和 CLIP score 通常依赖外部模型或第三方工具.
    - 本项目只接收标准化 metric rows, 不把重型指标模型塞入默认测试路径.

    项目特定写法:
    - `formal_result_claim=False` 表示该导入仅证明接口、字段和结果包链路.
    - 当 `formal_result_claim=True` 时, 必须提供外部运行日志、配置或摘要文件作为证据.
    """
    materialized_rows = [dict(row) for row in rows]
    materialized_evidence_paths = [str(path) for path in evidence_paths]
    if formal_result_claim and not materialized_evidence_paths:
        raise ValueError("formal metric import requires at least one evidence path")
    metric_fields = sorted(
        {
            key
            for row in materialized_rows
            for key in row
            if key in STANDARD_METRIC_COLUMNS
        }
    )
    advanced_metric_fields = sorted({"lpips", "fid", "clip_score"} & set(metric_fields))
    method_names = sorted({str(row["method_name"]) for row in materialized_rows if row.get("method_name")})
    baseline_ids = sorted({str(row["baseline_id"]) for row in materialized_rows if row.get("baseline_id")})
    return {
        "artifact_name": METRIC_ROW_IMPORT_MANIFEST_NAME,
        "producer_id": producer_id,
        "producer_role": "offline_external_metric_row_import",
        "formal_result_claim": bool(formal_result_claim),
        "execution_boundary": (
            "offline_external_metric_evidence_provided"
            if formal_result_claim
            else "offline_metric_row_import_requires_separate_formal_evidence"
        ),
        "source_metric_rows_path": str(source_metric_rows_path),
        "metric_rows_path": str(output_metric_rows_path),
        "metric_row_count": len(materialized_rows),
        "metric_fields": metric_fields,
        "advanced_metric_fields": advanced_metric_fields,
        "method_names": method_names,
        "baseline_ids": baseline_ids,
        "evidence_paths": materialized_evidence_paths,
        "execution_digest": build_stable_digest(
            {
                "rows": materialized_rows,
                "source_metric_rows_path": str(source_metric_rows_path),
                "formal_result_claim": bool(formal_result_claim),
                "evidence_paths": materialized_evidence_paths,
            }
        ),
    }


def _record_metric_key(row: dict[str, Any]) -> tuple[str, str]:
    """构造 records 侧的匹配键。"""
    return (str(row.get("event_id")), str(row.get("method_name") or row.get("baseline_id") or "ceg"))


def _metric_row_key(row: dict[str, Any]) -> tuple[str, str]:
    """构造指标文件侧的匹配键。"""
    return (str(row.get("event_id")), str(row.get("method_name") or row.get("baseline_id") or "ceg"))


def _base_image_event_id(event_id: str) -> str:
    """从派生事件 ID 中还原 image pair 级别 ID, 便于把图像质量指标合并到 positive_source 事件。"""

    for marker in ("__positive_source", "__clean_negative"):
        if event_id.endswith(marker):
            return event_id[: -len(marker)]
    return event_id


def _is_ceg_method(method_name: str) -> bool:
    """判断 method_name 是否属于 CEG 主方法或内部消融方法。"""

    return method_name == "ceg" or method_name.startswith("ceg_")


def merge_metric_rows_into_records(
    records: Iterable[dict[str, Any]],
    metric_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按 event_id + method_name / baseline_id 将高级指标合并进 records。"""
    metrics_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    metrics_by_image_id: dict[str, dict[str, Any]] = {}
    for row in metric_rows:
        metric_values = {key: value for key, value in row.items() if key in STANDARD_METRIC_COLUMNS}
        key = _metric_row_key(row)
        metrics_by_key.setdefault(key, {}).update(metric_values)
        metrics_by_image_id.setdefault(str(row.get("event_id")), {}).update(metric_values)
    merged: list[dict[str, Any]] = []
    for record in records:
        output = dict(record)
        method_name = str(output.get("method_name") or output.get("baseline_id") or "ceg")
        exact_metrics = metrics_by_key.get(_record_metric_key(output), {})
        output.update(exact_metrics)
        if not exact_metrics and _is_ceg_method(method_name):
            sample_role = str(output.get("sample_role") or "")
            attack_family = str(output.get("attack_family") or "clean")
            if sample_role == "positive_source" and attack_family == "clean":
                output.update(metrics_by_image_id.get(_base_image_event_id(str(output.get("event_id"))), {}))
        merged.append(output)
    return merged
