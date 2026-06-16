"""生成检测 ROC 曲线、score 分布和 operating point 表。

该模块消费统一 records 中的检测分数和真实水印标签, 用于生成论文常见的曲线类产物。
这些产物属于结果重建层: 它们不改变 CEG 判定, 只把已有事件事实转成可画图、可审计的曲线数据。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

DEFAULT_SCORE_BIN_COUNT = 10


def _is_number(value: Any) -> bool:
    """判断值是否为可统计数值, 显式排除 bool。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _method_name(row: dict[str, Any]) -> str:
    """读取方法名称。"""
    return str(row.get("method_name") or "unknown_method")


def _as_bool(value: Any) -> bool | None:
    """读取显式布尔标签。"""
    return value if isinstance(value, bool) else None


def score_for_detection(row: dict[str, Any]) -> float | None:
    """读取统一检测分数。

    CEG 记录优先使用 content_score_raw, 外部 baseline 记录优先使用 baseline_score。
    当 baseline 声明 higher_is_positive=False 时取相反数, 使曲线方向统一为“分数越高越像正例”。
    """
    if _is_number(row.get("baseline_score")):
        score = float(row["baseline_score"])
        return score if bool(row.get("higher_is_positive", True)) else -score
    if _is_number(row.get("content_score_raw")):
        return float(row["content_score_raw"])
    return None


def _scored_method_rows(rows: Iterable[dict[str, Any]]) -> dict[str, list[tuple[float, bool]]]:
    """按方法收集分数和真实标签。"""
    grouped: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("all rows must be dict")
        score = score_for_detection(row)
        label = _as_bool(row.get("is_watermarked"))
        if score is None or label is None:
            continue
        grouped[_method_name(row)].append((score, label))
    return grouped


def build_detection_roc_curve_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建 ROC 曲线长表。

    每个方法输出一组 threshold、tpr、fpr 点。数据不足时仍输出空结果而不是伪造曲线。
    """
    table_rows: list[dict[str, Any]] = []
    for method_name, scored_rows in sorted(_scored_method_rows(rows).items()):
        positives = [item for item in scored_rows if item[1]]
        negatives = [item for item in scored_rows if not item[1]]
        if not positives or not negatives:
            continue
        thresholds = [float("inf"), *sorted({score for score, _ in scored_rows}, reverse=True), float("-inf")]
        for point_index, threshold in enumerate(thresholds):
            true_positive = sum(1 for score, label in scored_rows if label and score >= threshold)
            false_positive = sum(1 for score, label in scored_rows if not label and score >= threshold)
            tpr = true_positive / len(positives)
            fpr = false_positive / len(negatives)
            if threshold == float("inf"):
                threshold_label = "above_max"
                threshold_value = None
            elif threshold == float("-inf"):
                threshold_label = "below_min"
                threshold_value = None
            else:
                threshold_label = "score_threshold"
                threshold_value = threshold
            table_rows.append(
                {
                    "method_name": method_name,
                    "point_index": point_index,
                    "threshold_label": threshold_label,
                    "threshold_value": threshold_value,
                    "tpr": tpr,
                    "fpr": fpr,
                    "true_positive_count": true_positive,
                    "false_positive_count": false_positive,
                    "positive_count": len(positives),
                    "negative_count": len(negatives),
                }
            )
    return table_rows


def build_score_histogram_table(rows: Iterable[dict[str, Any]], *, bin_count: int = DEFAULT_SCORE_BIN_COUNT) -> list[dict[str, Any]]:
    """构建检测分数分布直方表。"""
    if bin_count < 1:
        raise ValueError("bin_count must be >= 1")
    materialized = [dict(row) for row in rows]
    scores = [score for row in materialized for score in [score_for_detection(row)] if score is not None]
    if not scores:
        return []
    minimum = min(scores)
    maximum = max(scores)
    width = (maximum - minimum) / bin_count if maximum > minimum else 1.0
    grouped_counts: dict[tuple[str, str, int], int] = defaultdict(int)
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in materialized:
        score = score_for_detection(row)
        label = _as_bool(row.get("is_watermarked"))
        if score is None or label is None:
            continue
        method_name = _method_name(row)
        label_name = "watermarked" if label else "clean_or_negative"
        bin_index = min(int((score - minimum) / width), bin_count - 1) if width > 0 else 0
        grouped_counts[(method_name, label_name, bin_index)] += 1
        totals[(method_name, label_name)] += 1
    table_rows: list[dict[str, Any]] = []
    for (method_name, label_name, bin_index), count in sorted(grouped_counts.items()):
        total = totals[(method_name, label_name)]
        lower = minimum + bin_index * width
        upper = lower + width
        table_rows.append(
            {
                "method_name": method_name,
                "label_name": label_name,
                "bin_index": bin_index,
                "score_bin_lower": lower,
                "score_bin_upper": upper,
                "score_bin_count": count,
                "score_bin_rate": count / total if total else None,
            }
        )
    return table_rows


def _default_operating_threshold(method_rows: list[dict[str, Any]]) -> float | None:
    """从记录中推断默认 operating threshold。"""
    thresholds = [float(row["baseline_threshold"]) for row in method_rows if _is_number(row.get("baseline_threshold"))]
    if thresholds:
        return thresholds[0]
    thresholds = []
    for row in method_rows:
        payload_threshold = row.get("content_threshold_value")
        if _is_number(payload_threshold):
            thresholds.append(float(payload_threshold))
    if thresholds:
        return thresholds[0]
    return 0.5


def build_operating_point_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建默认 operating point 表。

    表中记录每个方法在默认阈值处的 TPR、FPR、TP/FP/TN/FN, 便于论文报告可复现的阈值选择点。
    """
    materialized = [dict(row) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        grouped[_method_name(row)].append(row)
    table_rows: list[dict[str, Any]] = []
    for method_name, method_rows in sorted(grouped.items()):
        threshold = _default_operating_threshold(method_rows)
        scored_rows = []
        for row in method_rows:
            score = score_for_detection(row)
            label = _as_bool(row.get("is_watermarked"))
            if score is not None and label is not None:
                scored_rows.append((score, label))
        positives = [item for item in scored_rows if item[1]]
        negatives = [item for item in scored_rows if not item[1]]
        if threshold is None or not scored_rows:
            continue
        true_positive = sum(1 for score, label in scored_rows if label and score >= threshold)
        false_positive = sum(1 for score, label in scored_rows if not label and score >= threshold)
        false_negative = len(positives) - true_positive
        true_negative = len(negatives) - false_positive
        table_rows.append(
            {
                "method_name": method_name,
                "operating_threshold": threshold,
                "positive_count": len(positives),
                "negative_count": len(negatives),
                "true_positive_count": true_positive,
                "false_positive_count": false_positive,
                "true_negative_count": true_negative,
                "false_negative_count": false_negative,
                "tpr": true_positive / len(positives) if positives else None,
                "fpr": false_positive / len(negatives) if negatives else None,
            }
        )
    return table_rows


def build_detection_curve_artifacts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """构建检测曲线类论文产物集合。"""
    materialized = [dict(row) for row in rows]
    return {
        "detection_roc_curve.csv": build_detection_roc_curve_table(materialized),
        "score_histogram_table.csv": build_score_histogram_table(materialized),
        "operating_point_table.csv": build_operating_point_table(materialized),
    }
