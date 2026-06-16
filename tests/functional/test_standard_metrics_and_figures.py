"""验证论文标准指标和图表规格可以由 records 重建。"""

from __future__ import annotations

import pytest

from main.analysis.figure_specs import build_paper_figure_specs
from main.analysis.rebuild_artifacts import build_all_paper_artifacts, write_artifact_bundle
from main.analysis.standard_metrics import aggregate_standard_watermark_metrics


def _rows() -> list[dict[str, object]]:
    """构造同时覆盖 CEG、外部 baseline、bit 指标和质量指标的轻量 records。"""
    return [
        {
            "event_id": "p1",
            "method_name": "ceg",
            "sample_role": "positive_source",
            "attack_family": "rotation",
            "is_watermarked": True,
            "final_decision": True,
            "content_score_raw": 0.91,
            "positive_by_content": True,
            "positive_by_geo_rescue": False,
            "rescue_eligible": False,
            "bit_correct_count": 95,
            "bit_total_count": 100,
            "payload_recovered": True,
            "psnr": 42.0,
            "ssim": 0.98,
            "lpips": 0.04,
            "fid": 8.0,
            "clip_score": 0.31,
        },
        {
            "event_id": "p2",
            "method_name": "ceg",
            "sample_role": "positive_source",
            "attack_family": "crop",
            "is_watermarked": True,
            "final_decision": True,
            "content_score_raw": 0.49,
            "positive_by_content": False,
            "positive_by_geo_rescue": True,
            "rescue_eligible": True,
            "bit_correct_count": 85,
            "bit_total_count": 100,
            "payload_recovered": True,
            "psnr": 40.0,
            "ssim": 0.96,
            "lpips": 0.06,
            "fid": 9.0,
            "clip_score": 0.3,
        },
        {
            "event_id": "n1",
            "method_name": "ceg",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "is_watermarked": False,
            "final_decision": False,
            "content_score_raw": 0.1,
            "positive_by_content": False,
            "positive_by_geo_rescue": False,
            "rescue_eligible": False,
            "psnr": 41.0,
            "ssim": 0.97,
            "lpips": 0.05,
            "fid": 8.5,
            "clip_score": 0.32,
        },
        {
            "event_id": "p1",
            "method_name": "tree_ring",
            "sample_role": "positive_source",
            "attack_family": "rotation",
            "is_watermarked": True,
            "final_decision": True,
            "baseline_score": 0.8,
            "baseline_threshold": 0.5,
            "higher_is_positive": True,
            "bit_accuracy": 0.9,
            "payload_recovered": True,
            "psnr": 39.0,
            "ssim": 0.95,
        },
        {
            "event_id": "n1",
            "method_name": "tree_ring",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "is_watermarked": False,
            "final_decision": False,
            "baseline_score": 0.2,
            "baseline_threshold": 0.5,
            "higher_is_positive": True,
            "bit_accuracy": 0.5,
            "payload_recovered": False,
            "psnr": 39.5,
            "ssim": 0.94,
        },
    ]


@pytest.mark.quick
def test_standard_watermark_metrics_cover_detection_bit_and_quality() -> None:
    """标准指标应同时覆盖检测、bit recovery 和图像质量三类论文结果。"""
    metrics = aggregate_standard_watermark_metrics(_rows())["by_method"]

    assert metrics["ceg"]["bit_accuracy"] == pytest.approx(0.9)
    assert metrics["ceg"]["bit_error_rate"] == pytest.approx(0.1)
    assert metrics["ceg"]["payload_recovery_rate"] == pytest.approx(1.0)
    assert metrics["ceg"]["quality_metrics"]["psnr"]["mean"] == pytest.approx(41.0)
    assert metrics["tree_ring"]["detection_auroc"] == pytest.approx(1.0)


@pytest.mark.quick
def test_all_paper_artifacts_include_standard_metrics_and_figure_specs(tmp_path) -> None:
    """完整论文产物集合应包含标准指标表和可渲染图表规格。"""
    artifacts = build_all_paper_artifacts(_rows(), content_thresholds={"ceg": 0.5})
    manifest = write_artifact_bundle(tmp_path, artifacts)

    assert "standard_watermark_metrics.json" in artifacts
    assert "quality_metrics_summary.csv" in artifacts
    assert "method_group_comparison_table.csv" in artifacts
    assert "bit_recovery_metrics.csv" in artifacts
    assert "attack_family_metrics.csv" in artifacts
    assert "paper_figure_specs.json" in artifacts
    assert "paper_figure_specs.json" in manifest["artifact_names"]
    assert (tmp_path / "quality_metrics_summary.csv").exists()


@pytest.mark.quick
def test_figure_specs_bind_claims_to_visible_data() -> None:
    """图表规格应为主表、救回、质量权衡、攻击家族和 bit recovery 提供数据。"""
    specs = build_paper_figure_specs(_rows())
    figure_ids = {figure["figure_id"] for figure in specs["figures"]}

    assert {
        "main_detection_comparison",
        "rescue_ablation_contribution",
        "quality_detection_tradeoff",
        "attack_family_robustness",
        "bit_recovery_comparison",
    } <= figure_ids
    for figure in specs["figures"]:
        assert figure["data"]
        assert figure["encodings"]


@pytest.mark.quick
def test_protocol_records_preserve_standard_metrics_for_ceg_and_baseline() -> None:
    """协议运行时应把 CEG payload 和 baseline metadata 中的标准指标提升到 records。"""
    from experiments.protocol_runner import run_paper_protocol

    rows = [
        {
            "event_id": "event_metric",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "rotation",
            "attack_condition": "rotation_light",
            "is_watermarked": True,
            "payload": {
                "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                "content": {"content_score_raw": 0.8},
                "geometry": {
                    "registration_confidence": 0.9,
                    "anchor_inlier_ratio": 0.8,
                    "recovered_sync_consistency": 0.8,
                },
                "attestation": {"attestation_score": 0.9},
                "standard_metrics": {
                    "bit_correct_count": 9,
                    "bit_total_count": 10,
                    "payload_recovered": True,
                    "psnr": 41.0,
                    "ssim": 0.97,
                },
                "baseline_observations": [
                    {
                        "baseline_id": "tree_ring",
                        "score": 0.7,
                        "threshold": 0.5,
                        "metadata": {
                            "bit_accuracy": "0.8",
                            "payload_recovered": "true",
                            "psnr": "39.0",
                            "ssim": "0.95",
                        },
                    }
                ],
            },
        }
    ]

    result = run_paper_protocol(rows, profile="paper_main_probe", content_thresholds={"ceg": 0.5})
    records = {record["method_name"]: record for record in result["records"]}

    assert records["ceg"]["bit_correct_count"] == pytest.approx(9.0)
    assert records["ceg"]["psnr"] == pytest.approx(41.0)
    assert records["tree_ring"]["bit_accuracy"] == pytest.approx(0.8)
    assert records["tree_ring"]["payload_recovered"] is True
    assert "standard_watermark_metrics.json" in result["all_paper_artifacts"]
