"""聚合图像水印论文常用标准指标。

该模块只消费已经进入 records 的事件级字段, 不直接读取图像文件。
这样设计的主要考虑在于: 真实图像质量指标、bit-level 解码结果和第三方 baseline
输出可以由不同实验 backend 产生, 但论文表格与图表应统一从 records 重建。
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Iterable

from main.analysis.aggregation import aggregate_decision_rows


QUALITY_METRIC_FIELDS = ("psnr", "ssim", "lpips", "fid", "clip_score")
FPR_TARGETS = (0.01, 0.001)


def _is_number(value: Any) -> bool:
    """判断字段是否是可用于统计的普通数值, 显式排除 bool。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_float(value: Any) -> float | None:
    """把可选数值字段转换为 float, 缺失或类型不匹配时返回 None。"""
    return float(value) if _is_number(value) else None


def _as_bool(value: Any) -> bool | None:
    """读取可选布尔字段, 避免把字符串或数字误当作正式布尔记录。"""
    return value if isinstance(value, bool) else None


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    """计算可空比例, 分母为 0 时返回 None 表示该指标无覆盖。"""
    return float(numerator / denominator) if denominator else None


def _method_name(row: dict[str, Any]) -> str:
    """读取方法名, 缺失时使用稳定占位名称以便审计异常输入。"""
    return str(row.get("method_name") or "unknown_method")


def _score_for_detection(row: dict[str, Any]) -> float | None:
    """读取用于阈值扫描的检测分数。

    CEG 记录优先使用 `content_score_raw`, baseline 记录优先使用 `baseline_score`。
    当 baseline 声明 `higher_is_positive=False` 时, 对分数取相反数, 让后续排序仍保持“越大越像正例”。
    """
    if _is_number(row.get("baseline_score")):
        score = float(row["baseline_score"])
        return score if bool(row.get("higher_is_positive", True)) else -score
    if _is_number(row.get("content_score_raw")):
        return float(row["content_score_raw"])
    return None


def _auroc(scored_rows: list[tuple[float, bool]]) -> float | None:
    """用秩统计计算 AUROC, 数据不足时返回 None。"""
    positives = [item for item in scored_rows if item[1]]
    negatives = [item for item in scored_rows if not item[1]]
    if not positives or not negatives:
        return None
    sorted_rows = sorted(scored_rows, key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(sorted_rows):
        next_index = index + 1
        while next_index < len(sorted_rows) and sorted_rows[next_index][0] == sorted_rows[index][0]:
            next_index += 1
        average_rank = (index + 1 + next_index) / 2.0
        for tied_index in range(index, next_index):
            if sorted_rows[tied_index][1]:
                rank_sum += average_rank
        index = next_index
    positive_count = len(positives)
    negative_count = len(negatives)
    return (rank_sum - positive_count * (positive_count + 1) / 2.0) / (positive_count * negative_count)


def _tpr_at_fpr(scored_rows: list[tuple[float, bool]], target_fpr: float) -> float | None:
    """在给定 FPR 上限下扫描阈值并返回可达到的最大 TPR。"""
    positives = [item for item in scored_rows if item[1]]
    negatives = [item for item in scored_rows if not item[1]]
    if not positives or not negatives:
        return None
    thresholds = sorted({score for score, _ in scored_rows}, reverse=True)
    best_tpr = 0.0
    for threshold in thresholds:
        true_positive = sum(1 for score, label in scored_rows if label and score >= threshold)
        false_positive = sum(1 for score, label in scored_rows if not label and score >= threshold)
        fpr = false_positive / len(negatives)
        if fpr <= target_fpr:
            best_tpr = max(best_tpr, true_positive / len(positives))
    return best_tpr


def _bit_counts(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """汇总 bit-level 正确数和总数, 只统计同时存在两个计数字段的记录。"""
    correct = 0
    total = 0
    for row in rows:
        if _is_number(row.get("bit_correct_count")) and _is_number(row.get("bit_total_count")):
            row_total = int(row["bit_total_count"])
            if row_total < 0:
                continue
            row_correct = int(row["bit_correct_count"])
            correct += max(0, min(row_correct, row_total))
            total += row_total
    return correct, total


def _mean_field(rows: list[dict[str, Any]], field_name: str) -> tuple[float | None, float]:
    """计算字段均值和覆盖率, 覆盖率用于提醒读者该指标是否来自完整 records。"""
    values = [float(row[field_name]) for row in rows if _is_number(row.get(field_name))]
    coverage = len(values) / len(rows) if rows else 0.0
    return (mean(values) if values else None), coverage


def aggregate_standard_watermark_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """按方法聚合检测、bit recovery 和图像质量标准指标。"""
    materialized = [dict(row) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        grouped[_method_name(row)].append(row)
    decision_summaries = aggregate_decision_rows(materialized)

    by_method: dict[str, dict[str, Any]] = {}
    for method_name, method_rows in sorted(grouped.items()):
        scored_rows = []
        for row in method_rows:
            score = _score_for_detection(row)
            label = _as_bool(row.get("is_watermarked"))
            if score is not None and label is not None:
                scored_rows.append((score, label))
        bit_correct_count, bit_total_count = _bit_counts(method_rows)
        bit_accuracy_from_counts = _safe_ratio(bit_correct_count, bit_total_count)
        bit_accuracy_mean, bit_accuracy_coverage = _mean_field(method_rows, "bit_accuracy")
        bit_accuracy = bit_accuracy_from_counts if bit_accuracy_from_counts is not None else bit_accuracy_mean
        payload_recovered_values = [_as_bool(row.get("payload_recovered")) for row in method_rows]
        payload_recovered_values = [value for value in payload_recovered_values if value is not None]
        quality_metrics = {
            field_name: {"mean": metric_mean, "coverage_rate": coverage_rate}
            for field_name in QUALITY_METRIC_FIELDS
            for metric_mean, coverage_rate in [_mean_field(method_rows, field_name)]
        }
        summary = decision_summaries.get(method_name, {})
        by_method[method_name] = {
            "event_count": len(method_rows),
            "tpr": summary.get("tpr"),
            "clean_fpr": summary.get("clean_fpr"),
            "attacked_negative_fpr": summary.get("attacked_negative_fpr"),
            "detection_auroc": _auroc(scored_rows),
            "tpr_at_fpr_1_percent": _tpr_at_fpr(scored_rows, FPR_TARGETS[0]),
            "tpr_at_fpr_0_1_percent": _tpr_at_fpr(scored_rows, FPR_TARGETS[1]),
            "bit_correct_count": bit_correct_count,
            "bit_total_count": bit_total_count,
            "bit_accuracy": bit_accuracy,
            "bit_error_rate": (1.0 - bit_accuracy) if bit_accuracy is not None else None,
            "bit_accuracy_coverage_rate": bit_accuracy_coverage if bit_accuracy_from_counts is None else 1.0,
            "payload_recovery_rate": (
                sum(1 for value in payload_recovered_values if value) / len(payload_recovered_values)
                if payload_recovered_values else None
            ),
            "payload_recovery_coverage_rate": len(payload_recovered_values) / len(method_rows) if method_rows else 0.0,
            "quality_metrics": quality_metrics,
        }
    return {"artifact_name": "standard_watermark_metrics.json", "by_method": by_method}


def build_quality_metrics_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """构造按方法和质量指标展开的长表, 便于论文表格和图表复用。"""
    materialized = [dict(row) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        grouped[_method_name(row)].append(row)
    table_rows: list[dict[str, Any]] = []
    for method_name, method_rows in sorted(grouped.items()):
        for metric_name in QUALITY_METRIC_FIELDS:
            metric_mean, coverage_rate = _mean_field(method_rows, metric_name)
            table_rows.append(
                {
                    "method_name": method_name,
                    "metric_name": metric_name,
                    "metric_mean": metric_mean,
                    "metric_coverage_rate": coverage_rate,
                    "event_count": len(method_rows),
                }
            )
    return table_rows


def build_bit_recovery_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """构造 bit recovery 指标表, 支持 CEG 与外部 baseline 对比。"""
    metrics = aggregate_standard_watermark_metrics(rows)["by_method"]
    return [
        {
            "method_name": method_name,
            "event_count": summary["event_count"],
            "bit_correct_count": summary["bit_correct_count"],
            "bit_total_count": summary["bit_total_count"],
            "bit_accuracy": summary["bit_accuracy"],
            "bit_error_rate": summary["bit_error_rate"],
            "payload_recovery_rate": summary["payload_recovery_rate"],
            "payload_recovery_coverage_rate": summary["payload_recovery_coverage_rate"],
        }
        for method_name, summary in sorted(metrics.items())
    ]


def build_attack_family_metrics_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 attack_family 聚合鲁棒性指标, 为旋转、缩放、裁剪等分层图表提供数据。"""
    materialized = [dict(row) for row in rows]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        grouped[(_method_name(row), str(row.get("attack_family") or "unknown_attack_family"))].append(row)
    table_rows: list[dict[str, Any]] = []
    for (method_name, attack_family), group_rows in sorted(grouped.items()):
        summary = aggregate_decision_rows(group_rows).get(method_name, {})
        bit_correct_count, bit_total_count = _bit_counts(group_rows)
        bit_accuracy = _safe_ratio(bit_correct_count, bit_total_count)
        table_rows.append(
            {
                "method_name": method_name,
                "attack_family": attack_family,
                "event_count": len(group_rows),
                "tpr": summary.get("tpr", 0.0),
                "clean_fpr": summary.get("clean_fpr", 0.0),
                "attacked_negative_fpr": summary.get("attacked_negative_fpr", 0.0),
                "final_positive_count": summary.get("final_positive_count", 0),
                "bit_accuracy": bit_accuracy,
            }
        )
    return table_rows
