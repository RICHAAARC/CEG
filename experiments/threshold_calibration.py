"""从 calibration 样本校准 CEG 内容阈值。

该模块只根据样本清单中已经存在的内容分数和样本角色生成阈值文件。它不重新运行模型,
也不把阈值写入正式论文结果; 阈值文件仍然会作为 `build_paper_outputs.py` 的显式输入进入产物链路。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from main.core.digest import build_stable_digest
from main.methods.ceg.ablations import CEG_ABLATIONS

DEFAULT_METHOD_NAME = "ceg"
DEFAULT_SCORE_FIELD = "content_score_raw"
DEFAULT_CALIBRATION_SPLIT = "calibration"
DEFAULT_NEGATIVE_ROLES = ("clean_negative",)
DEFAULT_TARGET_FPR = 0.01


def _is_number(value: Any) -> bool:
    """判断字段是否为普通数值, 显式排除 bool。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_float(value: Any) -> float | None:
    """把样本清单字段转为 float, 空值或非数值返回 None。"""
    if value is None or value == "":
        return None
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _row_method_name(row: dict[str, Any]) -> str:
    """读取样本行对应的方法名, 缺省时归入 CEG 主方法。"""
    return str(row.get("method_name") or DEFAULT_METHOD_NAME)


def _calibration_negative_scores(
    sample_rows: Iterable[dict[str, Any]],
    *,
    score_field: str,
    calibration_split: str,
    negative_roles: tuple[str, ...],
) -> dict[str, list[float]]:
    """按 method_name 收集 calibration negative 分数。"""
    grouped: dict[str, list[float]] = defaultdict(list)
    negative_role_set = set(negative_roles)
    for row in sample_rows:
        if not isinstance(row, dict):
            raise TypeError("sample rows must be dict")
        if str(row.get("split")) != calibration_split:
            continue
        if str(row.get("sample_role")) not in negative_role_set:
            continue
        score = _as_float(row.get(score_field))
        if score is None:
            continue
        grouped[_row_method_name(row)].append(score)
    return grouped


def threshold_for_target_fpr(scores: list[float], *, target_fpr: float, epsilon: float = 1e-12) -> float:
    """根据 negative 分数生成满足目标 FPR 上界的阈值。

    判定规则是 `score >= threshold` 视为 positive。若校准集太小导致允许误报数为0,
    阈值会被设置为略高于最大 negative 分数, 从而避免 clean calibration 集上产生误报。
    """
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


def build_threshold_calibration_report(
    sample_rows: Iterable[dict[str, Any]],
    *,
    target_fpr: float = DEFAULT_TARGET_FPR,
    score_field: str = DEFAULT_SCORE_FIELD,
    calibration_split: str = DEFAULT_CALIBRATION_SPLIT,
    negative_roles: tuple[str, ...] = DEFAULT_NEGATIVE_ROLES,
    include_ceg_ablations: bool = True,
) -> dict[str, Any]:
    """构建阈值映射和校准审计报告。"""
    materialized = [dict(row) for row in sample_rows]
    grouped_scores = _calibration_negative_scores(
        materialized,
        score_field=score_field,
        calibration_split=calibration_split,
        negative_roles=negative_roles,
    )
    if DEFAULT_METHOD_NAME not in grouped_scores and grouped_scores:
        # 若样本清单没有显式 method_name=ceg, 使用所有 calibration negative 合并后校准 CEG 主阈值。
        grouped_scores[DEFAULT_METHOD_NAME] = [score for scores in grouped_scores.values() for score in scores]
    if DEFAULT_METHOD_NAME not in grouped_scores:
        raise ValueError("no calibration negative scores available for ceg threshold calibration")

    thresholds: dict[str, float] = {}
    by_method: dict[str, dict[str, Any]] = {}
    for method_name, scores in sorted(grouped_scores.items()):
        threshold = threshold_for_target_fpr(scores, target_fpr=target_fpr)
        false_positive_count = sum(1 for score in scores if score >= threshold)
        thresholds[method_name] = threshold
        by_method[method_name] = {
            "method_name": method_name,
            "score_field": score_field,
            "calibration_split": calibration_split,
            "negative_roles": list(negative_roles),
            "negative_score_count": len(scores),
            "target_fpr": target_fpr,
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
    report = {
        "artifact_name": "threshold_calibration_report.json",
        "overall_decision": "pass",
        "target_fpr": target_fpr,
        "score_field": score_field,
        "calibration_split": calibration_split,
        "negative_roles": list(negative_roles),
        "thresholds": thresholds,
        "by_method": by_method,
        "sample_row_count": len(materialized),
    }
    report["threshold_calibration_digest"] = build_stable_digest(
        {
            "target_fpr": target_fpr,
            "score_field": score_field,
            "calibration_split": calibration_split,
            "negative_roles": list(negative_roles),
            "thresholds": thresholds,
            "by_method": by_method,
        }
    )
    return report


def write_threshold_calibration_outputs(
    sample_rows: Iterable[dict[str, Any]],
    output_root: str | Path,
    *,
    target_fpr: float = DEFAULT_TARGET_FPR,
    score_field: str = DEFAULT_SCORE_FIELD,
    calibration_split: str = DEFAULT_CALIBRATION_SPLIT,
    negative_roles: tuple[str, ...] = DEFAULT_NEGATIVE_ROLES,
) -> dict[str, Any]:
    """写出 thresholds.json 和 threshold_calibration_report.json。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    report = build_threshold_calibration_report(
        sample_rows,
        target_fpr=target_fpr,
        score_field=score_field,
        calibration_split=calibration_split,
        negative_roles=negative_roles,
    )
    (output_path / "thresholds.json").write_text(
        json.dumps(report["thresholds"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_path / "threshold_calibration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
