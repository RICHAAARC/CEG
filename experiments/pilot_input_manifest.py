"""定义并校验 pilot 论文结果包输入 manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.baseline_file_adapter import load_baseline_observation_rows
from experiments.metric_file_adapter import load_metric_rows
from experiments.detection_plan import validate_detection_output_root

PILOT_INPUT_MANIFEST_NAME = "pilot_input_manifest.json"

REQUIRED_PILOT_INPUT_FIELDS = ("events", "thresholds")

OPTIONAL_PILOT_INPUT_FIELDS = (
    "baseline_observations",
    "baseline_execution_manifest",
    "metric_rows",
    "metric_execution_manifest",
    "detection_execution_manifest",
    "image_pairs",
    "attacked_image_manifest",
    "attack_shard_manifest",
    "experiment_matrix",
    "readiness_requirements",
)


def load_pilot_input_manifest(path: str | Path) -> dict[str, Any]:
    """读取 pilot 输入 manifest."""
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("pilot input manifest must contain an object")
    return dict(payload)


def _resolve_path(base_dir: Path, value: Any) -> Path | None:
    """把 manifest 中的相对路径解析为相对 manifest 所在目录的绝对路径."""
    if value is None or str(value).strip() == "":
        return None
    path = Path(str(value))
    return path if path.is_absolute() else base_dir / path


def _load_json(path: Path) -> Any:
    """读取 JSON 文件."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check_json_list(path: Path, field_name: str) -> dict[str, Any]:
    """校验 JSON 文件是否为数组."""
    try:
        payload = _load_json(path)
        return {
            "field": field_name,
            "path": str(path),
            "status": "pass" if isinstance(payload, list) else "fail",
            "row_count": len(payload) if isinstance(payload, list) else None,
            "reason": None if isinstance(payload, list) else "json_payload_not_list",
        }
    except Exception as exc:
        return {"field": field_name, "path": str(path), "status": "fail", "reason": str(exc)}


def _check_json_dict(path: Path, field_name: str) -> dict[str, Any]:
    """校验 JSON 文件是否为对象."""
    try:
        payload = _load_json(path)
        return {
            "field": field_name,
            "path": str(path),
            "status": "pass" if isinstance(payload, dict) else "fail",
            "key_count": len(payload) if isinstance(payload, dict) else None,
            "reason": None if isinstance(payload, dict) else "json_payload_not_object",
        }
    except Exception as exc:
        return {"field": field_name, "path": str(path), "status": "fail", "reason": str(exc)}


def validate_pilot_input_manifest(path: str | Path) -> dict[str, Any]:
    """校验 pilot 输入 manifest 是否足以进入一键结果包构建.

    通用工程写法:
    - 先校验路径存在和基本文件形态, 再交给正式 builder 重建表格和结果包.
    - 可选产物缺失不阻断 dry-run, 但会在 checks 中明确记录.

    项目特定写法:
    - `events` 与 `thresholds` 是构建 paper outputs 的最小必需输入.
    - baseline / metric / detection / image manifest 是论文结果包增强证据.
    """
    manifest_path = Path(path)
    manifest = load_pilot_input_manifest(manifest_path)
    base_dir = manifest_path.parent
    checks: list[dict[str, Any]] = []
    resolved_inputs: dict[str, str | None] = {}

    for field in REQUIRED_PILOT_INPUT_FIELDS:
        candidate = _resolve_path(base_dir, manifest.get(field))
        resolved_inputs[field] = str(candidate) if candidate else None
        if candidate is None:
            checks.append({"field": field, "status": "fail", "reason": "required_field_missing"})
        elif not candidate.is_file():
            checks.append({"field": field, "path": str(candidate), "status": "fail", "reason": "file_missing"})
        elif field == "events":
            checks.append(_check_json_list(candidate, field))
        elif field == "thresholds":
            checks.append(_check_json_dict(candidate, field))

    for field in OPTIONAL_PILOT_INPUT_FIELDS:
        candidate = _resolve_path(base_dir, manifest.get(field))
        resolved_inputs[field] = str(candidate) if candidate else None
        if candidate is None:
            checks.append({"field": field, "status": "skip", "reason": "optional_field_absent"})
            continue
        if not candidate.is_file():
            checks.append({"field": field, "path": str(candidate), "status": "fail", "reason": "file_missing"})
            continue
        if field in {"image_pairs", "experiment_matrix"}:
            checks.append(_check_json_list(candidate, field))
        elif field in {
            "baseline_execution_manifest",
            "metric_execution_manifest",
            "detection_execution_manifest",
            "attacked_image_manifest",
            "attack_shard_manifest",
            "readiness_requirements",
        }:
            checks.append(_check_json_dict(candidate, field))
        elif field == "baseline_observations":
            try:
                rows = load_baseline_observation_rows(candidate)
                checks.append({"field": field, "path": str(candidate), "status": "pass", "row_count": len(rows)})
            except Exception as exc:
                checks.append({"field": field, "path": str(candidate), "status": "fail", "reason": str(exc)})
        elif field == "metric_rows":
            try:
                rows = load_metric_rows(candidate)
                checks.append({"field": field, "path": str(candidate), "status": "pass", "row_count": len(rows)})
            except Exception as exc:
                checks.append({"field": field, "path": str(candidate), "status": "fail", "reason": str(exc)})

    detection_root_value = manifest.get("detection_output_root")
    detection_root = _resolve_path(base_dir, detection_root_value)
    if detection_root is not None:
        resolved_inputs["detection_output_root"] = str(detection_root)
        try:
            contract = validate_detection_output_root(detection_root)
            checks.append(
                {
                    "field": "detection_output_root",
                    "path": str(detection_root),
                    "status": contract["overall_decision"],
                    "evidence": contract,
                }
            )
        except Exception as exc:
            checks.append({"field": "detection_output_root", "path": str(detection_root), "status": "fail", "reason": str(exc)})
    else:
        resolved_inputs["detection_output_root"] = None
        checks.append({"field": "detection_output_root", "status": "skip", "reason": "optional_field_absent"})

    fail_count = sum(1 for check in checks if check["status"] == "fail")
    pass_count = sum(1 for check in checks if check["status"] == "pass")
    skip_count = sum(1 for check in checks if check["status"] == "skip")
    return {
        "artifact_name": "pilot_input_manifest_validation.json",
        "manifest_path": str(manifest_path),
        "overall_decision": "fail" if fail_count else "pass",
        "resolved_inputs": resolved_inputs,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "fail_count": fail_count,
            "pass_count": pass_count,
            "skip_count": skip_count,
        },
    }
