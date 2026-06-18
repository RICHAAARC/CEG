"""生成 fixed-FPR 阈值校准与 TPR@FPR 论文表格。

该模块属于结果重建层, 只消费已经由实验流程产生的统一 records。
它不会调用图像模型, 不会改变 CEG 判定算法, 也不会伪造正式实验结果。
在其他项目中可复用的部分是: 先用 calibration clean negative 分数确定阈值,
再在 test split 上分别统计 clean positive 与 attacked positive 的 TPR。
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from main.analysis.detection_curves import score_for_detection

DEFAULT_TARGET_FPRS = (0.01, 0.001)


def _is_bool(value: Any) -> bool:
    """判断字段是否为显式布尔值, 避免把 0 / 1 误当作标签。"""
    return isinstance(value, bool)


def _method_name(row: dict[str, Any]) -> str:
    """读取方法名, 缺失时使用稳定的 unknown_method 便于审计。"""
    return str(row.get("method_name") or "unknown_method")


def _split_name(row: dict[str, Any]) -> str:
    """读取数据划分名, 缺失时按 test 处理以兼容早期 dry-run records。"""
    return str(row.get("split") or "test")


def _sample_role(row: dict[str, Any]) -> str:
    """读取样本角色, 该字段用于区分正例、clean 负例和攻击负例。"""
    return str(row.get("sample_role") or "unknown_role")


def _attack_family(row: dict[str, Any]) -> str:
    """读取攻击族, 缺失时视为 clean。"""
    return str(row.get("attack_family") or "clean")


def _is_watermarked(row: dict[str, Any]) -> bool | None:
    """读取真实水印标签, 只有显式 bool 才参与 fixed-FPR 统计。"""
    value = row.get("is_watermarked")
    return value if _is_bool(value) else None


def _scored_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取具有可比较检测分数和真实标签的行。

    CEG 与外部 baseline 的分数方向由 score_for_detection 统一处理,
    因此后续逻辑只需要使用“分数越高越像正例”的约定。
    """
    output: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise TypeError("all rows must be dict")
        row = dict(raw_row)
        score = score_for_detection(row)
        label = _is_watermarked(row)
        if score is None or label is None:
            continue
        row["_fixed_fpr_score"] = float(score)
        row["_fixed_fpr_label"] = bool(label)
        output.append(row)
    return output


def threshold_for_target_fpr(negative_scores: Iterable[float], target_fpr: float) -> float | None:
    """从 calibration clean negative 分数计算满足目标 FPR 的阈值。

    该函数采用保守策略: 阈值选择在负例分数之间, 尽量保证校准集上的
    false positive rate 不超过 target_fpr。负例数量不足时返回 None,
    由上层表格显式记录无法校准, 而不是生成虚假阈值。
    """
    scores = sorted((float(score) for score in negative_scores), reverse=True)
    if not scores:
        return None
    if target_fpr < 0 or target_fpr > 1:
        raise ValueError("target_fpr must be between 0 and 1")
    allowed_false_positive = math.floor(len(scores) * target_fpr)
    if allowed_false_positive <= 0:
        return scores[0] + 1e-12
    if allowed_false_positive >= len(scores):
        return scores[-1] - 1e-12
    upper = scores[allowed_false_positive - 1]
    lower = scores[allowed_false_positive]
    return (upper + lower) / 2.0


def _rate_at_threshold(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """在给定阈值处统计阳性率和计数。

    对正例集合该 rate 等价于 TPR, 对负例集合该 rate 等价于 FPR。
    """
    count = len(rows)
    positive_count = sum(1 for row in rows if float(row["_fixed_fpr_score"]) >= threshold)
    return {
        "sample_count": count,
        "positive_count_at_threshold": positive_count,
        "rate_at_threshold": positive_count / count if count else None,
    }


def _clean_negative_rows(method_rows: list[dict[str, Any]], *, split: str | None = None) -> list[dict[str, Any]]:
    """筛选 clean negative 行, 可选择限制在指定 split。"""
    return [
        row
        for row in method_rows
        if (split is None or _split_name(row) == split)
        and _sample_role(row) == "clean_negative"
        and _is_watermarked(row) is False
    ]


def _positive_rows(
    method_rows: list[dict[str, Any]],
    *,
    split: str,
    attacked_only: bool | None = None,
) -> list[dict[str, Any]]:
    """筛选正例行, attacked_only 用于区分 clean 正例和攻击后正例。"""
    if attacked_only is True:
        return [
            row
            for row in method_rows
            if _split_name(row) == split
            and _sample_role(row) == "attacked_positive"
            and _attack_family(row) != "clean"
            and _is_watermarked(row) is True
        ]
    if attacked_only is False:
        return [
            row
            for row in method_rows
            if _split_name(row) == split
            and _sample_role(row) == "positive_source"
            and _attack_family(row) == "clean"
            and _is_watermarked(row) is True
        ]
    return [
        row
        for row in method_rows
        if _split_name(row) == split
        and _sample_role(row) in {"positive_source", "attacked_positive"}
        and _is_watermarked(row) is True
    ]


def build_fixed_fpr_artifacts(
    rows: Iterable[dict[str, Any]],
    *,
    target_fprs: Iterable[float] = DEFAULT_TARGET_FPRS,
) -> dict[str, list[dict[str, Any]]]:
    """构建 fixed-FPR 阈值表、总体 TPR@FPR 表和攻击分组 TPR@FPR 表。"""
    materialized = _scored_rows(rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        grouped[_method_name(row)].append(row)

    threshold_rows: list[dict[str, Any]] = []
    tpr_rows: list[dict[str, Any]] = []
    attack_rows: list[dict[str, Any]] = []
    for method_name, method_rows in sorted(grouped.items()):
        calibration_negatives = _clean_negative_rows(method_rows, split="calibration")
        calibration_source = "calibration_clean_negative"
        if not calibration_negatives:
            calibration_negatives = _clean_negative_rows(method_rows)
            calibration_source = "fallback_all_clean_negative"
        test_negatives = _clean_negative_rows(method_rows, split="test") or _clean_negative_rows(method_rows)
        clean_positives = _positive_rows(method_rows, split="test", attacked_only=False)
        all_test_positives = _positive_rows(method_rows, split="test", attacked_only=None)
        attacked_positives = _positive_rows(method_rows, split="test", attacked_only=True)
        if not clean_positives:
            clean_positives = all_test_positives

        negative_scores = [float(row["_fixed_fpr_score"]) for row in calibration_negatives]
        for target_fpr in target_fprs:
            threshold = threshold_for_target_fpr(negative_scores, float(target_fpr))
            calibration_false_positive_count = sum(
                1 for score in negative_scores if threshold is not None and score >= threshold
            )
            threshold_rows.append(
                {
                    "method_name": method_name,
                    "target_fpr": float(target_fpr),
                    "threshold_value": threshold,
                    "calibration_source": calibration_source,
                    "calibration_negative_count": len(calibration_negatives),
                    "calibration_false_positive_count": calibration_false_positive_count,
                    "calibration_observed_fpr": (
                        calibration_false_positive_count / len(negative_scores)
                        if negative_scores and threshold is not None
                        else None
                    ),
                }
            )
            if threshold is None:
                tpr_rows.append(
                    {
                        "method_name": method_name,
                        "target_fpr": float(target_fpr),
                        "threshold_value": None,
                        "test_clean_negative_count": len(test_negatives),
                        "test_fpr_at_threshold": None,
                        "test_positive_count": len(clean_positives),
                        "tpr_at_fixed_fpr": None,
                    }
                )
                continue
            negative_rate = _rate_at_threshold(test_negatives, threshold)
            positive_rate = _rate_at_threshold(clean_positives, threshold)
            tpr_rows.append(
                {
                    "method_name": method_name,
                    "target_fpr": float(target_fpr),
                    "threshold_value": threshold,
                    "test_clean_negative_count": negative_rate["sample_count"],
                    "test_false_positive_count": negative_rate["positive_count_at_threshold"],
                    "test_fpr_at_threshold": negative_rate["rate_at_threshold"],
                    "test_positive_count": positive_rate["sample_count"],
                    "test_true_positive_count": positive_rate["positive_count_at_threshold"],
                    "tpr_at_fixed_fpr": positive_rate["rate_at_threshold"],
                }
            )
            by_attack: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in attacked_positives:
                by_attack[_attack_family(row)].append(row)
            for attack_family, attack_method_rows in sorted(by_attack.items()):
                attack_rate = _rate_at_threshold(attack_method_rows, threshold)
                attack_rows.append(
                    {
                        "method_name": method_name,
                        "target_fpr": float(target_fpr),
                        "threshold_value": threshold,
                        "attack_family": attack_family,
                        "attacked_positive_count": attack_rate["sample_count"],
                        "attacked_true_positive_count": attack_rate["positive_count_at_threshold"],
                        "attack_tpr_at_fixed_fpr": attack_rate["rate_at_threshold"],
                    }
                )
    return {
        "fixed_fpr_threshold_table.csv": threshold_rows,
        "tpr_at_fixed_fpr_table.csv": tpr_rows,
        "attack_tpr_at_fixed_fpr_table.csv": attack_rows,
    }
