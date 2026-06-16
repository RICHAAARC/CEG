"""验证论文 supported claims 审计产物。"""

from __future__ import annotations

import pytest

from experiments.metric_file_adapter import merge_metric_rows_into_records
from experiments.paper_fixture_factory import build_paper_dry_run_inputs
from experiments.protocol_runner import run_paper_protocol
from main.analysis.claim_audit import build_paper_claim_audit
from main.analysis.rebuild_artifacts import build_all_paper_artifacts


@pytest.mark.quick
def test_claim_audit_passes_for_full_dry_run_records() -> None:
    """完整 dry-run 应能证明论文核心声明均绑定到受治理产物。"""
    bundle = build_paper_dry_run_inputs()
    result = run_paper_protocol(
        bundle["events"],
        profile="paper_main_probe",
        content_thresholds=bundle["thresholds"],
        baseline_observation_rows=bundle["baseline_observations"],
    )
    records = merge_metric_rows_into_records(result["records"], bundle["metric_rows"])
    artifacts = build_all_paper_artifacts(records, content_thresholds=bundle["thresholds"])

    claim_audit = artifacts["paper_claim_audit.json"]

    assert claim_audit["overall_decision"] == "pass"
    assert claim_audit["supported_claim_count"] == claim_audit["claim_count"]
    claim_ids = {claim["claim_id"] for claim in claim_audit["claims"]}
    assert "external_baseline_comparison_supported" in claim_ids
    assert "standard_watermark_metrics_supported" in claim_ids
    assert "paper_figures_supported" in claim_ids


@pytest.mark.quick
def test_claim_audit_reports_missing_external_baseline_support() -> None:
    """缺少外部 baseline records 时, claim audit 必须显式失败而不是静默通过。"""
    rows = [
        {"method_name": "ceg", "sample_role": "positive_source", "final_decision": True, "is_watermarked": True},
        {"method_name": "ceg", "sample_role": "clean_negative", "final_decision": False, "is_watermarked": False},
    ]
    artifacts = {
        "formal_final_decision_metrics.json": {"by_method": {"ceg": {}}},
        "formal_main_table.csv": [{"method_name": "ceg", "tpr": 1.0, "clean_fpr": 0.0}],
        "baseline_comparison_table.csv": [{"method_name": "ceg", "tpr": 1.0, "clean_fpr": 0.0}],
        "standard_watermark_metrics.json": {"by_method": {"ceg": {}}},
        "paper_figure_specs.json": {"figures": []},
    }

    claim_audit = build_paper_claim_audit(rows, artifacts)
    external_claim = next(
        claim for claim in claim_audit["claims"] if claim["claim_id"] == "external_baseline_comparison_supported"
    )

    assert claim_audit["overall_decision"] == "fail"
    assert external_claim["status"] == "fail"
    assert "tree_ring" in external_claim["missing_methods"]
