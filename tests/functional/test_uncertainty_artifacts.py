"""验证论文率指标置信区间和方法差值产物。"""

from __future__ import annotations

import pytest

from main.analysis.rebuild_artifacts import build_all_paper_artifacts
from main.analysis.uncertainty import build_method_pairwise_delta_table, build_rate_confidence_interval_table


@pytest.mark.quick
def test_rate_confidence_interval_table_uses_wilson_bounds() -> None:
    """率指标置信区间表应包含点估计、上下界和计数。"""
    rows = [
        {"method_name": "ceg", "sample_role": "positive_source", "final_decision": True},
        {"method_name": "ceg", "sample_role": "positive_source", "final_decision": False},
        {"method_name": "ceg", "sample_role": "clean_negative", "final_decision": False},
        {"method_name": "tree_ring", "sample_role": "positive_source", "final_decision": True},
        {"method_name": "tree_ring", "sample_role": "clean_negative", "final_decision": True},
    ]

    table = build_rate_confidence_interval_table(rows)
    ceg_tpr = next(row for row in table if row["method_name"] == "ceg" and row["metric_name"] == "tpr")

    assert ceg_tpr["success_count"] == 1
    assert ceg_tpr["total_count"] == 2
    assert ceg_tpr["rate_value"] == pytest.approx(0.5)
    assert 0.0 <= ceg_tpr["ci_lower"] <= ceg_tpr["rate_value"] <= ceg_tpr["ci_upper"] <= 1.0
    assert ceg_tpr["ci_method"] == "wilson_95_percent"


@pytest.mark.quick
def test_pairwise_delta_table_compares_methods_to_ceg() -> None:
    """方法差值表应按 metric_name 给出相对 CEG 的点估计差值。"""
    rows = [
        {"method_name": "ceg", "sample_role": "positive_source", "final_decision": True},
        {"method_name": "ceg", "sample_role": "clean_negative", "final_decision": False},
        {"method_name": "tree_ring", "sample_role": "positive_source", "final_decision": False},
        {"method_name": "tree_ring", "sample_role": "clean_negative", "final_decision": True},
    ]

    table = build_method_pairwise_delta_table(rows, reference_method="ceg")
    tree_tpr = next(row for row in table if row["method_name"] == "tree_ring" and row["metric_name"] == "tpr")

    assert tree_tpr["reference_method"] == "ceg"
    assert tree_tpr["method_rate_value"] == pytest.approx(0.0)
    assert tree_tpr["reference_rate_value"] == pytest.approx(1.0)
    assert tree_tpr["rate_delta"] == pytest.approx(-1.0)
    assert tree_tpr["delta_ci_lower"] <= tree_tpr["rate_delta"] <= tree_tpr["delta_ci_upper"]


@pytest.mark.quick
def test_all_paper_artifacts_include_uncertainty_tables_and_figure_specs() -> None:
    """完整 artifact 构建器应输出不确定性表, figure specs 也应包含置信区间图。"""
    rows = [
        {"method_name": "ceg", "sample_role": "positive_source", "final_decision": True, "is_watermarked": True},
        {"method_name": "ceg", "sample_role": "clean_negative", "final_decision": False, "is_watermarked": False},
        {"method_name": "tree_ring", "sample_role": "positive_source", "final_decision": False, "is_watermarked": True},
        {"method_name": "tree_ring", "sample_role": "clean_negative", "final_decision": True, "is_watermarked": False},
    ]

    artifacts = build_all_paper_artifacts(rows, content_thresholds={"ceg": 0.5})
    figure_ids = {figure["figure_id"] for figure in artifacts["paper_figure_specs.json"]["figures"]}

    assert "rate_confidence_intervals.csv" in artifacts
    assert "method_pairwise_delta_table.csv" in artifacts
    assert "detection_confidence_intervals" in figure_ids
