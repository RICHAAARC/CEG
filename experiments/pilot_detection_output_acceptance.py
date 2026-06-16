"""校验 detection pilot 输出是否可进入 fixed-FPR 统计和论文结果包构建。

该模块位于 experiments 层, 用于接收真实 CEG detector、外部 detector command plan 或当前轻量
producer 已经写出的 detection 结果。它只检查 detection events、thresholds 和执行 manifest 的文件
契约与统计可用性, 不运行检测模型, 不重新计算分数, 也不把 dry-run producer 输出声明为正式论文结果。

通用工程写法是: 在统计阶段之前检查事件记录是否包含标签、分数、split 和样本角色。
项目特定写法是: 按 CEG 与 CEG-WM 对齐的 fixed-FPR 口径, 明确 calibration clean negative、
test clean negative、test positive 和 attacked positive 是否存在。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.detection_plan import (
    DETECTION_EVENTS_NAME,
    DETECTION_EXECUTION_MANIFEST_NAME,
    DETECTION_THRESHOLDS_NAME,
    validate_detection_output_root,
)
from experiments.ceg_detection_producer import DETECTION_PRODUCER_MANIFEST_NAME
from main.analysis.detection_curves import score_for_detection

REPORT_NAME = "pilot_detection_output_acceptance_report.json"
NEXT_STAGE_ON_PASS = "fixed_fpr_statistics_pilot"
NEXT_STAGE_ON_FAIL = "run_detection_backend_and_fix_outputs"
REQUIRED_DETECTION_EVENT_FIELDS = (
    "event_id",
    "method_name",
    "split",
    "sample_role",
    "attack_family",
    "attack_condition",
    "is_watermarked",
)


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _payload_content_score(row: dict[str, Any]) -> float | None:
    """兼容未扁平化 CEG event, 读取 payload.content.content_score_raw。"""
    score = score_for_detection(row)
    if score is not None:
        return float(score)
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if not isinstance(content, dict):
        return None
    value = content.get("content_score_raw")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _manifest_check(output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """检查 detection 执行 manifest 或 producer manifest 是否存在。"""
    specs = [
        {
            "relative_path": DETECTION_EXECUTION_MANIFEST_NAME,
            "manifest_role": "external_or_formal_detection_execution",
        },
        {
            "relative_path": DETECTION_PRODUCER_MANIFEST_NAME,
            "manifest_role": "lightweight_detection_contract_producer",
        },
    ]
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    selected: str | None = None
    for spec in specs:
        path = output_root / str(spec["relative_path"])
        payload, error = _read_json(path) if path.is_file() else (None, "missing_manifest_file")
        check = {
            "relative_path": spec["relative_path"],
            "path": str(path),
            "manifest_role": spec["manifest_role"],
            "exists": path.is_file(),
            "readable_json": error is None,
            "json_error": error,
            "artifact_name": payload.get("artifact_name") if isinstance(payload, dict) else None,
            "formal_result_claim": payload.get("formal_result_claim") if isinstance(payload, dict) else None,
        }
        checks.append(check)
        if error is None and selected is None:
            selected = str(spec["relative_path"])
    if selected is None:
        issues.append(
            {
                "issue_type": "missing_detection_run_manifest",
                "accepted_manifest_names": [DETECTION_EXECUTION_MANIFEST_NAME, DETECTION_PRODUCER_MANIFEST_NAME],
            }
        )
    return checks, issues, selected


def _event_role_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    """按 fixed-FPR 所需角色统计 detection events。"""
    counts = {
        "calibration_clean_negative": 0,
        "test_clean_negative": 0,
        "test_positive": 0,
        "test_attacked_positive": 0,
        "scored_event_count": 0,
    }
    for row in events:
        score = _payload_content_score(row)
        if score is not None and isinstance(row.get("is_watermarked"), bool):
            counts["scored_event_count"] += 1
        split = str(row.get("split") or "")
        role = str(row.get("sample_role") or "")
        label = row.get("is_watermarked")
        attack_family = str(row.get("attack_family") or "clean")
        if split == "calibration" and role == "clean_negative" and label is False:
            counts["calibration_clean_negative"] += 1
        if split == "test" and role == "clean_negative" and label is False:
            counts["test_clean_negative"] += 1
        if split == "test" and label is True and role in {"positive_source", "attacked_positive"}:
            counts["test_positive"] += 1
        if split == "test" and label is True and role == "attacked_positive" and attack_family != "clean":
            counts["test_attacked_positive"] += 1
    return counts


def _build_event_checks(events_payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """校验 detection_events.json 事件字段与统计可用性。"""
    if not isinstance(events_payload, list):
        return [], [{"issue_type": "detection_events_not_list"}], {
            "calibration_clean_negative": 0,
            "test_clean_negative": 0,
            "test_positive": 0,
            "test_attacked_positive": 0,
            "scored_event_count": 0,
        }
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    materialized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(events_payload):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "detection_event_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        materialized.append(row)
        score = _payload_content_score(row)
        missing_fields = [
            field for field in REQUIRED_DETECTION_EVENT_FIELDS if row.get(field) is None or str(row.get(field)).strip() == ""
        ]
        row_check = {
            "row_index": index,
            "event_id": row.get("event_id") or f"event_{index + 1:04d}",
            "method_name": row.get("method_name"),
            "split": row.get("split"),
            "sample_role": row.get("sample_role"),
            "attack_family": row.get("attack_family"),
            "attack_condition": row.get("attack_condition"),
            "is_watermarked_is_bool": isinstance(row.get("is_watermarked"), bool),
            "score": score,
            "has_usable_score": score is not None,
            "missing_fields": missing_fields,
        }
        checks.append(row_check)
        for field in missing_fields:
            issues.append({"issue_type": "missing_detection_event_field", "row_index": index, "field_name": field})
        if not isinstance(row.get("is_watermarked"), bool):
            issues.append({"issue_type": "invalid_is_watermarked_label", "row_index": index})
        if score is None:
            issues.append({"issue_type": "missing_detection_score", "row_index": index})
    role_counts = _event_role_counts(materialized)
    if role_counts["scored_event_count"] == 0:
        issues.append({"issue_type": "no_scored_detection_events"})
    # 这些角色是 fixed-FPR 主统计所需的最小集合。当前 dry-run 若缺 calibration clean negative 会失败, 这是正确阻断。
    for role_name in ("calibration_clean_negative", "test_clean_negative", "test_positive"):
        if role_counts[role_name] == 0:
            issues.append({"issue_type": "missing_fixed_fpr_required_role", "role_name": role_name})
    return checks, issues, role_counts


def _build_threshold_checks(thresholds_payload: Any, event_checks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验 detection_thresholds.json 是否覆盖事件中的 method_name。"""
    if not isinstance(thresholds_payload, dict):
        return [], [{"issue_type": "detection_thresholds_not_object"}]
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    method_names = sorted({str(item["method_name"]) for item in event_checks if item.get("method_name")})
    for method_name in method_names:
        has_threshold = method_name in thresholds_payload
        value = thresholds_payload.get(method_name)
        valid_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        checks.append(
            {
                "method_name": method_name,
                "has_threshold": has_threshold,
                "threshold_value": value,
                "threshold_is_numeric": valid_number,
            }
        )
        if not has_threshold:
            issues.append({"issue_type": "missing_method_threshold", "method_name": method_name})
        elif not valid_number:
            issues.append({"issue_type": "non_numeric_method_threshold", "method_name": method_name})
    if not thresholds_payload:
        issues.append({"issue_type": "empty_detection_thresholds"})
    return checks, issues


def build_pilot_detection_output_acceptance_report(output_root: str | Path) -> dict[str, Any]:
    """构建 detection 输出接收门禁报告。"""
    root = Path(output_root)
    try:
        required_contract = validate_detection_output_root(root)
    except Exception as exc:
        required_contract = {
            "output_root": str(root),
            "overall_decision": "fail",
            "missing_required_outputs": [],
            "event_count": 0,
            "threshold_count": 0,
            "checks": [],
            "contract_error": f"{type(exc).__name__}: {exc}",
        }
    issues: list[dict[str, Any]] = [
        {"issue_type": "missing_required_detection_output", "relative_path": relative}
        for relative in required_contract.get("missing_required_outputs", [])
    ]
    if required_contract.get("contract_error"):
        issues.append({"issue_type": "detection_output_contract_error", "error": required_contract["contract_error"]})
    events_path = root / DETECTION_EVENTS_NAME
    thresholds_path = root / DETECTION_THRESHOLDS_NAME
    events_payload, events_error = _read_json(events_path) if events_path.is_file() else (None, "missing_detection_events")
    thresholds_payload, thresholds_error = _read_json(thresholds_path) if thresholds_path.is_file() else (
        None,
        "missing_detection_thresholds",
    )
    if events_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_detection_events", "path": str(events_path), "error": events_error})
    if thresholds_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_detection_thresholds", "path": str(thresholds_path), "error": thresholds_error})
    manifest_checks, manifest_issues, selected_manifest = _manifest_check(root)
    event_checks, event_issues, role_counts = _build_event_checks(events_payload)
    threshold_checks, threshold_issues = _build_threshold_checks(thresholds_payload, event_checks)
    issues.extend(manifest_issues)
    issues.extend(event_issues)
    issues.extend(threshold_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "required_detection_outputs": [DETECTION_EVENTS_NAME, DETECTION_THRESHOLDS_NAME],
        "required_output_contract": required_contract,
        "events_path": str(events_path),
        "events_readable_json": events_error is None,
        "events_json_error": events_error,
        "thresholds_path": str(thresholds_path),
        "thresholds_readable_json": thresholds_error is None,
        "thresholds_json_error": thresholds_error,
        "selected_run_manifest": selected_manifest,
        "run_manifest_checks": manifest_checks,
        "event_checks": event_checks,
        "threshold_checks": threshold_checks,
        "fixed_fpr_role_counts": role_counts,
        "blocking_issues": issues,
        "summary": {
            "missing_required_output_count": len(required_contract.get("missing_required_outputs", [])),
            "event_count": len(events_payload) if isinstance(events_payload, list) else 0,
            "threshold_count": len(thresholds_payload) if isinstance(thresholds_payload, dict) else 0,
            "event_check_count": len(event_checks),
            "threshold_check_count": len(threshold_checks),
            "run_manifest_check_count": len(manifest_checks),
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_detection_output_acceptance_report(output_root: str | Path, out: str | Path) -> dict[str, Any]:
    """写出 detection 输出接收门禁报告。"""
    report = build_pilot_detection_output_acceptance_report(output_root)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
