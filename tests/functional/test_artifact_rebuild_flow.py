"""验证 PW02 / PW04 等价产物可由事件 records 重建。"""

from __future__ import annotations

import json

import pytest

from main.analysis.rebuild_artifacts import build_pw02_artifacts, build_pw04_tables, write_artifact_bundle


@pytest.mark.quick
def test_pw02_artifacts_are_rebuilt_from_records() -> None:
    """PW02 关键 JSON 产物必须由 records 和阈值输入生成。"""
    rows = [
        {"method_name": "ceg", "sample_role": "positive_source", "content_score_raw": 0.8, "final_decision": True},
        {"method_name": "ceg", "sample_role": "clean_negative", "content_score_raw": 0.2, "final_decision": False},
    ]

    artifacts = build_pw02_artifacts(rows, content_thresholds={"ceg": 0.5})

    assert set(artifacts) == {
        "formal_final_decision_metrics.json",
        "content_score_distribution_audit.json",
        "content_threshold_degeneracy_report.json",
    }
    report = artifacts["content_threshold_degeneracy_report.json"]["by_method"]["ceg"]
    assert report["content_threshold_degenerate"] is False
    assert report["content_threshold_degenerate_reason"] == "none"


@pytest.mark.quick
def test_pw04_tables_and_manifest_are_written_to_tmp_path(tmp_path) -> None:
    """PW04 表格和 manifest 应写入临时目录, 不依赖 checked-in outputs。"""
    rows = [
        {
            "method_name": "ceg",
            "sample_role": "positive_source",
            "final_decision": True,
            "positive_by_content": False,
            "positive_by_geo_rescue": True,
            "rescue_eligible": True,
        },
        {
            "method_name": "gaussian_shading",
            "sample_role": "positive_source",
            "final_decision": True,
        },
    ]

    artifacts = build_pw04_tables(rows)
    manifest = write_artifact_bundle(tmp_path, artifacts)

    assert "formal_main_table.csv" in manifest["artifact_names"]
    assert "rescue_metrics_summary.csv" in manifest["artifact_names"]
    assert "method_group_comparison_table.csv" in manifest["artifact_names"]
    loaded_manifest = json.loads((tmp_path / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert loaded_manifest["artifact_digest"]
    assert (tmp_path / "baseline_comparison_table.csv").exists()
    assert (tmp_path / "method_group_comparison_table.csv").exists()
    group_rows = artifacts["method_group_comparison_table.csv"]
    assert {row["method_group"] for row in group_rows} == {"ceg_primary", "external_baseline"}
