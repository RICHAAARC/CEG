"""生成论文率指标置信区间和方法间差值表。

该模块只消费已经进入 records 的事件级事实, 不重新运行 CEG 判定, 也不调用外部 baseline。
它提供论文主表常见的不确定性信息: TPR、clean FPR、attacked-negative FPR 的 Wilson 置信区间, 以及相对参考方法的差值区间。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

RATE_METRICS = ("tpr", "clean_fpr", "attacked_negative_fpr")
DEFAULT_REFERENCE_METHOD = "ceg"


def _as_bool(value: Any) -> bool:
    """读取显式布尔值, 非布尔值按 False 处理。"""
    return value if isinstance(value, bool) else False


def _method_name(row: dict[str, Any]) -> str:
    """读取方法名, 缺失时使用稳定兜底名称。"""
    return str(row.get("method_name") or "unknown_method")


def _wilson_interval(success_count: int, total_count: int, *, z_value: float = 1.96) -> tuple[float | None, float | None, float | None]:
    """计算 Wilson score 置信区间。

    该实现属于通用统计工程写法, 比直接使用 rate +/- 正态近似更适合小样本 dry-run 和 pilot 实验。
    """
    if total_count <= 0:
        return None, None, None
    rate = success_count / total_count
    z_squared = z_value * z_value
    denominator = 1.0 + z_squared / total_count
    centre = rate + z_squared / (2.0 * total_count)
    margin = z_value * ((rate * (1.0 - rate) + z_squared / (4.0 * total_count)) / total_count) ** 0.5
    lower = max(0.0, (centre - margin) / denominator)
    upper = min(1.0, (centre + margin) / denominator)
    return rate, lower, upper


def _metric_counts(method_rows: list[dict[str, Any]], metric_name: str) -> tuple[int, int]:
    """按指标定义计算成功数和分母。"""
    if metric_name == "tpr":
        eligible = [row for row in method_rows if row.get("sample_role") == "positive_source"]
    elif metric_name == "clean_fpr":
        eligible = [row for row in method_rows if row.get("sample_role") == "clean_negative"]
    elif metric_name == "attacked_negative_fpr":
        eligible = [row for row in method_rows if row.get("sample_role") == "attacked_negative"]
    else:
        raise ValueError(f"unsupported rate metric: {metric_name}")
    success_count = sum(1 for row in eligible if _as_bool(row.get("final_decision")))
    return success_count, len(eligible)


def build_rate_confidence_interval_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建按 method 和 metric 展开的 Wilson 置信区间长表。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("all rows must be dict")
        grouped[_method_name(row)].append(row)
    table_rows: list[dict[str, Any]] = []
    for method_name, method_rows in sorted(grouped.items()):
        for metric_name in RATE_METRICS:
            success_count, total_count = _metric_counts(method_rows, metric_name)
            rate, ci_lower, ci_upper = _wilson_interval(success_count, total_count)
            table_rows.append(
                {
                    "method_name": method_name,
                    "metric_name": metric_name,
                    "success_count": success_count,
                    "total_count": total_count,
                    "rate_value": rate,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                    "ci_method": "wilson_95_percent",
                }
            )
    return table_rows


def build_method_pairwise_delta_table(
    rows: Iterable[dict[str, Any]],
    *,
    reference_method: str = DEFAULT_REFERENCE_METHOD,
) -> list[dict[str, Any]]:
    """构建每个方法相对参考方法的率指标差值表。"""
    interval_rows = build_rate_confidence_interval_table(rows)
    by_key = {(row["method_name"], row["metric_name"]): row for row in interval_rows}
    output_rows: list[dict[str, Any]] = []
    for row in interval_rows:
        method_name = str(row["method_name"])
        metric_name = str(row["metric_name"])
        if method_name == reference_method:
            continue
        reference = by_key.get((reference_method, metric_name))
        if not reference:
            continue
        method_rate = row.get("rate_value")
        reference_rate = reference.get("rate_value")
        if method_rate is None or reference_rate is None:
            delta = None
            delta_lower = None
            delta_upper = None
        else:
            delta = float(method_rate) - float(reference_rate)
            delta_lower = (
                float(row["ci_lower"]) - float(reference["ci_upper"])
                if row.get("ci_lower") is not None and reference.get("ci_upper") is not None
                else None
            )
            delta_upper = (
                float(row["ci_upper"]) - float(reference["ci_lower"])
                if row.get("ci_upper") is not None and reference.get("ci_lower") is not None
                else None
            )
        output_rows.append(
            {
                "reference_method": reference_method,
                "method_name": method_name,
                "metric_name": metric_name,
                "method_rate_value": method_rate,
                "reference_rate_value": reference_rate,
                "rate_delta": delta,
                "delta_ci_lower": delta_lower,
                "delta_ci_upper": delta_upper,
                "ci_method": "wilson_95_percent_conservative_difference",
            }
        )
    return output_rows


def build_uncertainty_artifacts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """构建论文不确定性分析产物集合。"""
    materialized = [dict(row) for row in rows]
    return {
        "rate_confidence_intervals.csv": build_rate_confidence_interval_table(materialized),
        "method_pairwise_delta_table.csv": build_method_pairwise_delta_table(materialized),
    }
