"""验证检测曲线、分数分布和 operating point 产物。"""

from __future__ import annotations

import pytest

from main.analysis.detection_curves import (
    build_detection_roc_curve_table,
    build_operating_point_table,
    build_score_histogram_table,
)
from main.analysis.rebuild_artifacts import build_all_paper_artifacts


def _rows() -> list[dict[str, object]]:
    """构造同时包含 CEG 和 baseline 分数的轻量曲线测试数据。"""
    return [
        {"method_name": "ceg", "sample_role": "positive_source", "is_watermarked": True, "content_score_raw": 0.9, "final_decision": True},
        {"method_name": "ceg", "sample_role": "positive_source", "is_watermarked": True, "content_score_raw": 0.7, "final_decision": True},
        {"method_name": "ceg", "sample_role": "clean_negative", "is_watermarked": False, "content_score_raw": 0.2, "final_decision": False},
        {"method_name": "ceg", "sample_role": "attacked_negative", "is_watermarked": False, "content_score_raw": 0.4, "final_decision": False},
        {"method_name": "tree_ring", "sample_role": "positive_source", "is_watermarked": True, "baseline_score": 0.8, "baseline_threshold": 0.5, "final_decision": True},
        {"method_name": "tree_ring", "sample_role": "clean_negative", "is_watermarked": False, "baseline_score": 0.6, "baseline_threshold": 0.5, "final_decision": True},
        {"method_name": "tree_ring", "sample_role": "attacked_negative", "is_watermarked": False, "baseline_score": 0.3, "baseline_threshold": 0.5, "final_decision": False},
    ]


@pytest.mark.quick
def test_detection_roc_curve_table_contains_threshold_points() -> None:
    """ROC 表应按方法输出 fpr/tpr 阈值扫描点。"""
    table = build_detection_roc_curve_table(_rows())
    ceg_rows = [row for row in table if row["method_name"] == "ceg"]

    assert ceg_rows[0]["threshold_label"] == "above_max"
    assert ceg_rows[0]["tpr"] == pytest.approx(0.0)
    assert ceg_rows[-1]["threshold_label"] == "below_min"
    assert ceg_rows[-1]["fpr"] == pytest.approx(1.0)
    assert any(row["threshold_value"] == pytest.approx(0.7) for row in ceg_rows if row["threshold_value"] is not None)


@pytest.mark.quick
def test_score_histogram_table_groups_by_label_and_method() -> None:
    """score 分布表应同时保留方法名和正负标签分组。"""
    table = build_score_histogram_table(_rows(), bin_count=4)
    labels = {row["label_name"] for row in table}
    methods = {row["method_name"] for row in table}

    assert {"watermarked", "clean_or_negative"} <= labels
    assert {"ceg", "tree_ring"} <= methods
    assert all(row["score_bin_count"] >= 1 for row in table)


@pytest.mark.quick
def test_operating_point_table_uses_default_thresholds() -> None:
    """operating point 表应输出默认阈值下的混淆计数。"""
    table = build_operating_point_table(_rows())
    tree_ring = next(row for row in table if row["method_name"] == "tree_ring")

    assert tree_ring["operating_threshold"] == pytest.approx(0.5)
    assert tree_ring["true_positive_count"] == 1
    assert tree_ring["false_positive_count"] == 1
    assert tree_ring["fpr"] == pytest.approx(0.5)


@pytest.mark.quick
def test_all_paper_artifacts_include_detection_curve_outputs() -> None:
    """完整论文产物应包含检测曲线表和对应 figure specs。"""
    artifacts = build_all_paper_artifacts(_rows(), content_thresholds={"ceg": 0.5})
    figure_ids = {figure["figure_id"] for figure in artifacts["paper_figure_specs.json"]["figures"]}

    assert "detection_roc_curve.csv" in artifacts
    assert "score_histogram_table.csv" in artifacts
    assert "operating_point_table.csv" in artifacts
    assert "detection_roc_curves" in figure_ids
    assert "score_distribution_by_method" in figure_ids
