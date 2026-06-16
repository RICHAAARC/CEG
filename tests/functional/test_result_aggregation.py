"""验证结果聚合器可以同时消费 CEG 与 baseline 事件记录。"""

from __future__ import annotations

import pytest

from main.analysis.aggregation import aggregate_decision_rows


@pytest.mark.quick
def test_aggregate_decision_rows_exports_main_and_mechanism_metrics() -> None:
    """聚合器必须输出主表指标与机制 rescue 统计。"""
    rows = [
        {
            "method_name": "ceg",
            "sample_role": "positive_source",
            "final_decision": True,
            "positive_by_content": True,
            "positive_by_geo_rescue": False,
            "rescue_eligible": False,
        },
        {
            "method_name": "ceg",
            "sample_role": "positive_source",
            "final_decision": True,
            "positive_by_content": False,
            "positive_by_geo_rescue": True,
            "rescue_eligible": True,
        },
        {
            "method_name": "ceg",
            "sample_role": "clean_negative",
            "final_decision": False,
            "positive_by_content": False,
            "positive_by_geo_rescue": False,
            "rescue_eligible": False,
        },
        {
            "method_name": "tree_ring",
            "sample_role": "positive_source",
            "final_decision": True,
        },
    ]

    summary = aggregate_decision_rows(rows)

    assert summary["ceg"]["tpr"] == pytest.approx(1.0)
    assert summary["ceg"]["clean_fpr"] == pytest.approx(0.0)
    assert summary["ceg"]["positive_by_geo_rescue_count"] == 1
    assert summary["ceg"]["rescue_gain"] == 1
    assert summary["tree_ring"]["event_count"] == 1
