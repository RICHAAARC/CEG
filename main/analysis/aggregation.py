"""聚合 CEG 与外部 baseline 的事件级结果。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def _as_bool(row: dict[str, Any], key: str) -> bool:
    """从扁平事件行中读取布尔字段, 缺失时按 False 处理。"""
    value = row.get(key)
    return value if isinstance(value, bool) else False


def _safe_ratio(numerator: int, denominator: int) -> float:
    """计算安全比例, 分母为 0 时返回 0.0。"""
    return float(numerator / denominator) if denominator else 0.0


def aggregate_decision_rows(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按方法聚合主结果、误报率和 rescue 机制统计。

    输入行可以来自 CEG 事件 records, 也可以来自外部 baseline 适配器。baseline
    若没有机制字段, 对应 rescue 统计自然为 0。
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("all rows must be dict")
        method_name = str(row.get("method_name") or "unknown_method")
        grouped[method_name].append(row)

    summaries: dict[str, dict[str, Any]] = {}
    for method_name, method_rows in sorted(grouped.items()):
        positive_rows = [row for row in method_rows if row.get("sample_role") == "positive_source"]
        clean_negative_rows = [row for row in method_rows if row.get("sample_role") == "clean_negative"]
        attacked_negative_rows = [row for row in method_rows if row.get("sample_role") == "attacked_negative"]
        final_positive_count = sum(1 for row in method_rows if _as_bool(row, "final_decision"))
        final_negative_count = len(method_rows) - final_positive_count
        positive_by_content_count = sum(1 for row in method_rows if _as_bool(row, "positive_by_content"))
        positive_by_geo_rescue_count = sum(1 for row in method_rows if _as_bool(row, "positive_by_geo_rescue"))
        rescue_eligible_event_count = sum(1 for row in method_rows if _as_bool(row, "rescue_eligible"))
        geo_rescue_applied_event_count = positive_by_geo_rescue_count
        content_failed_subset_event_count = sum(
            1 for row in method_rows if row.get("sample_role") == "positive_source" and not _as_bool(row, "positive_by_content")
        )
        summaries[method_name] = {
            "event_count": len(method_rows),
            "final_positive_count": final_positive_count,
            "final_negative_count": final_negative_count,
            "tpr": _safe_ratio(
                sum(1 for row in positive_rows if _as_bool(row, "final_decision")),
                len(positive_rows),
            ),
            "clean_fpr": _safe_ratio(
                sum(1 for row in clean_negative_rows if _as_bool(row, "final_decision")),
                len(clean_negative_rows),
            ),
            "attacked_negative_fpr": _safe_ratio(
                sum(1 for row in attacked_negative_rows if _as_bool(row, "final_decision")),
                len(attacked_negative_rows),
            ),
            "content_failed_subset_event_count": content_failed_subset_event_count,
            "rescue_eligible_event_count": rescue_eligible_event_count,
            "geo_rescue_applied_event_count": geo_rescue_applied_event_count,
            "positive_by_content_count": positive_by_content_count,
            "positive_by_geo_rescue_count": positive_by_geo_rescue_count,
            "rescue_gain": final_positive_count - positive_by_content_count,
        }
    return summaries
