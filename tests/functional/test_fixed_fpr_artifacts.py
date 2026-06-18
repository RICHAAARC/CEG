"""验证 fixed-FPR 阈值校准和 TPR@FPR 论文表格。"""

from __future__ import annotations

import pytest

from main.analysis.fixed_fpr import build_fixed_fpr_artifacts, threshold_for_target_fpr
from main.analysis.rebuild_artifacts import build_all_paper_artifacts


def _rows() -> list[dict[str, object]]:
    """构造同时覆盖 calibration、test、clean 正例和 attacked 正例的轻量 records。"""
    return [
        {
            "method_name": "ceg",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "is_watermarked": False,
            "content_score_raw": 0.20,
        },
        {
            "method_name": "ceg",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "is_watermarked": False,
            "content_score_raw": 0.30,
        },
        {
            "method_name": "ceg",
            "split": "test",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "is_watermarked": False,
            "content_score_raw": 0.10,
        },
        {
            "method_name": "ceg",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "is_watermarked": True,
            "content_score_raw": 0.80,
        },
        {
            "method_name": "ceg",
            "split": "test",
            "sample_role": "attacked_positive",
            "attack_family": "jpeg",
            "is_watermarked": True,
            "content_score_raw": 0.70,
        },
    ]


@pytest.mark.quick
def test_threshold_for_target_fpr_is_conservative() -> None:
    """目标 FPR 很低时, 阈值应高于校准 clean negative 的最大分数。"""
    threshold = threshold_for_target_fpr([0.2, 0.3], 0.01)

    assert threshold is not None
    assert threshold > 0.3


@pytest.mark.quick
def test_fixed_fpr_artifacts_include_threshold_tpr_and_attack_tables() -> None:
    """fixed-FPR 产物应同时包含阈值表、总体 TPR 表和攻击分组 TPR 表。"""
    artifacts = build_fixed_fpr_artifacts(_rows(), target_fprs=(0.01,))

    threshold_row = artifacts["fixed_fpr_threshold_table.csv"][0]
    tpr_row = artifacts["tpr_at_fixed_fpr_table.csv"][0]
    attack_row = artifacts["attack_tpr_at_fixed_fpr_table.csv"][0]

    assert threshold_row["method_name"] == "ceg"
    assert threshold_row["calibration_source"] == "calibration_clean_negative"
    assert threshold_row["calibration_observed_fpr"] == pytest.approx(0.0)
    assert tpr_row["test_fpr_at_threshold"] == pytest.approx(0.0)
    assert tpr_row["tpr_at_fixed_fpr"] == pytest.approx(1.0)
    assert attack_row["attack_family"] == "jpeg"
    assert attack_row["attack_tpr_at_fixed_fpr"] == pytest.approx(1.0)


@pytest.mark.quick
def test_all_paper_artifacts_include_fixed_fpr_outputs() -> None:
    """完整论文产物重建应索引 fixed-FPR 与 TPR@FPR 表格。"""
    artifacts = build_all_paper_artifacts(_rows(), content_thresholds={"ceg": 0.5})

    assert "fixed_fpr_threshold_table.csv" in artifacts
    assert "tpr_at_fixed_fpr_table.csv" in artifacts
    assert "attack_tpr_at_fixed_fpr_table.csv" in artifacts
