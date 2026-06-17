"""对 detection events 执行 fixed FPR 阈值校准并回写事件 payload。

该模块解决一个关键衔接问题: `build_paper_outputs.py` 虽然接收 thresholds 文件用于 artifact 审计,
但 CEG formal decision 的实际阈值来自每个 event 的 `payload.thresholds`。因此真实 fixed FPR
校准必须生成一份已回写阈值的 detection events, 后续 protocol runner 才能按校准 operating point
计算 final decision 和 TPP@FPR。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from main.core.digest import build_stable_digest
from main.methods.ceg.ablations import CEG_ABLATIONS

DEFAULT_TARGET_FPR = 0.01
DEFAULT_SCORE_FIELD = "content_score_raw"
DEFAULT_CALIBRATION_SPLIT = "calibration"
DEFAULT_NEGATIVE_ROLES = ("clean_negative",)
DEFAULT_METHOD_NAME = "ceg"


def load_detection_events(path: str | Path) -> list[dict[str, Any]]:
    """读取 detection events JSON 数组。"""

    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("detection events JSON must contain a list")
    return [dict(row) for row in payload]


def calibrate_detection_event_thresholds(
    events: Iterable[dict[str, Any]],
    *,
    target_fpr: float = DEFAULT_TARGET_FPR,
    score_field: str = DEFAULT_SCORE_FIELD,
    calibration_split: str = DEFAULT_CALIBRATION_SPLIT,
    negative_roles: tuple[str, ...] = DEFAULT_NEGATIVE_ROLES,
    include_ceg_ablations: bool = True,
) -> dict[str, Any]:
    """根据 clean negative detection events 校准阈值并返回回写后的事件。"""

    materialized = [dict(event) for event in events]
    grouped_scores = _collect_negative_scores(
        materialized,
        score_field=score_field,
        calibration_split=calibration_split,
        negative_roles=negative_roles,
    )
    calibration_source = "calibration_clean_negative"
    if not grouped_scores:
        grouped_scores = _collect_negative_scores(
            materialized,
            score_field=score_field,
            calibration_split=None,
            negative_roles=negative_roles,
        )
        calibration_source = "fallback_all_clean_negative"
    if DEFAULT_METHOD_NAME not in grouped_scores and grouped_scores:
        grouped_scores[DEFAULT_METHOD_NAME] = [score for scores in grouped_scores.values() for score in scores]
    if DEFAULT_METHOD_NAME not in grouped_scores:
        raise ValueError("no clean negative detection events available for fixed FPR calibration")

    thresholds: dict[str, float] = {}
    by_method: dict[str, dict[str, Any]] = {}
    for method_name, scores in sorted(grouped_scores.items()):
        threshold = threshold_for_target_fpr(scores, target_fpr=target_fpr)
        false_positive_count = sum(1 for score in scores if score >= threshold)
        thresholds[method_name] = threshold
        by_method[method_name] = {
            "method_name": method_name,
            "score_field": score_field,
            "target_fpr": target_fpr,
            "calibration_split": calibration_split,
            "calibration_source": calibration_source,
            "negative_roles": list(negative_roles),
            "negative_score_count": len(scores),
            "allowed_false_positive_count": math.floor(target_fpr * len(scores)),
            "observed_false_positive_count": false_positive_count,
            "observed_fpr": false_positive_count / len(scores),
            "threshold": threshold,
            "score_min": min(scores),
            "score_max": max(scores),
        }
    if include_ceg_ablations:
        ceg_threshold = thresholds[DEFAULT_METHOD_NAME]
        for variant in CEG_ABLATIONS:
            thresholds.setdefault(f"ceg_{variant.lower().replace('-', '_')}", ceg_threshold)

    calibrated_events = [_with_calibrated_threshold(event, thresholds) for event in materialized]
    report = {
        "artifact_name": "detection_event_threshold_calibration_report.json",
        "overall_decision": "pass",
        "target_fpr": target_fpr,
        "score_field": score_field,
        "calibration_split": calibration_split,
        "calibration_source": calibration_source,
        "negative_roles": list(negative_roles),
        "thresholds": thresholds,
        "by_method": by_method,
        "event_count": len(materialized),
        "calibrated_event_count": len(calibrated_events),
    }
    report["threshold_calibration_digest"] = build_stable_digest(
        {
            "target_fpr": target_fpr,
            "score_field": score_field,
            "calibration_source": calibration_source,
            "thresholds": thresholds,
            "by_method": by_method,
        }
    )
    return {"events": calibrated_events, "thresholds": thresholds, "report": report}


def write_calibrated_detection_event_outputs(
    events: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    target_fpr: float = DEFAULT_TARGET_FPR,
    score_field: str = DEFAULT_SCORE_FIELD,
    calibration_split: str = DEFAULT_CALIBRATION_SPLIT,
    negative_roles: tuple[str, ...] = DEFAULT_NEGATIVE_ROLES,
) -> dict[str, Any]:
    """写出已校准 detection events、thresholds 和校准报告。"""

    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    result = calibrate_detection_event_thresholds(
        events,
        target_fpr=target_fpr,
        score_field=score_field,
        calibration_split=calibration_split,
        negative_roles=negative_roles,
    )
    events_path = output_path / "detection_events_calibrated.json"
    thresholds_path = output_path / "detection_thresholds_calibrated.json"
    report_path = output_path / "detection_event_threshold_calibration_report.json"
    events_path.write_text(json.dumps(result["events"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    thresholds_path.write_text(json.dumps(result["thresholds"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(result["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        **result["report"],
        "calibrated_events_path": events_path.as_posix(),
        "calibrated_thresholds_path": thresholds_path.as_posix(),
        "calibration_report_path": report_path.as_posix(),
    }


def threshold_for_target_fpr(scores: list[float], *, target_fpr: float, epsilon: float = 1e-12) -> float:
    """根据 negative 分数生成满足目标 FPR 上界的阈值。"""

    if not scores:
        raise ValueError("at least one calibration negative score is required")
    if target_fpr < 0 or target_fpr >= 1:
        raise ValueError("target_fpr must be in [0, 1)")
    sorted_scores = sorted(float(score) for score in scores)
    allowed_false_positive_count = math.floor(target_fpr * len(sorted_scores))
    if allowed_false_positive_count <= 0:
        return max(sorted_scores) + epsilon
    descending = sorted(sorted_scores, reverse=True)
    return descending[allowed_false_positive_count - 1]


def _collect_negative_scores(
    events: Iterable[dict[str, Any]],
    *,
    score_field: str,
    calibration_split: str | None,
    negative_roles: tuple[str, ...],
) -> dict[str, list[float]]:
    """按 method_name 收集 clean negative 分数。"""

    grouped: dict[str, list[float]] = {}
    negative_role_set = set(negative_roles)
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("events must be dict")
        if calibration_split is not None and str(event.get("split")) != calibration_split:
            continue
        if str(event.get("sample_role")) not in negative_role_set:
            continue
        if event.get("is_watermarked") is not False:
            continue
        score = _event_score(event, score_field=score_field)
        if score is None:
            continue
        method_name = str(event.get("method_name") or DEFAULT_METHOD_NAME)
        grouped.setdefault(method_name, []).append(score)
    return grouped


def _event_score(event: Mapping[str, Any], *, score_field: str) -> float | None:
    """从 detection event 中读取嵌套 content score。"""

    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        return None
    content = payload.get("content")
    if not isinstance(content, Mapping):
        return None
    value = content.get(score_field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _with_calibrated_threshold(event: dict[str, Any], thresholds: Mapping[str, float]) -> dict[str, Any]:
    """把校准阈值写回单个 event 的 payload.thresholds。"""

    updated = dict(event)
    payload = dict(updated.get("payload") or {})
    threshold_node = dict(payload.get("thresholds") or {})
    method_name = str(updated.get("method_name") or DEFAULT_METHOD_NAME)
    threshold_value = float(thresholds.get(method_name, thresholds[DEFAULT_METHOD_NAME]))
    threshold_node["content_threshold"] = threshold_value
    payload["thresholds"] = threshold_node
    source = dict(payload.get("detection_source") or {})
    source["fixed_fpr_calibrated"] = True
    source["fixed_fpr_content_threshold"] = threshold_value
    source["fixed_fpr_threshold_source"] = "detection_event_threshold_calibration"
    payload["detection_source"] = source
    updated["payload"] = payload
    return updated
