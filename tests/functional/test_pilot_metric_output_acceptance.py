"""验证 pilot quality metric 输出接收门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.metric_file_adapter import build_metric_row_import_manifest
from experiments.pilot_metric_output_acceptance import build_pilot_metric_output_acceptance_report


def _write_metric_outputs(root, rows: list[dict[str, object]]) -> None:
    """写出测试用 metric rows 与 execution manifest。"""
    root.mkdir(parents=True, exist_ok=True)
    rows_path = root / "metric_rows.json"
    rows_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    manifest = build_metric_row_import_manifest(
        rows,
        source_metric_rows_path=rows_path,
        output_metric_rows_path=rows_path,
        formal_result_claim=False,
        producer_id="test_metric_importer",
    )
    (root / "metric_execution_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


@pytest.mark.quick
def test_metric_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空 metric 输出目录必须失败, 避免未运行 metric 时进入统计和结果包阶段。"""
    report = build_pilot_metric_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_metric_backend_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 2
    assert report["summary"]["blocking_issue_count"] >= 2


@pytest.mark.quick
def test_metric_output_acceptance_passes_imported_metric_contract(tmp_path) -> None:
    """离线 metric importer 产出的标准 rows 与 manifest 应通过接收门禁。"""
    rows = [
        {
            "event_id": "event_001",
            "method_name": "ceg",
            "psnr": 31.5,
            "ssim": 0.91,
            "lpips": 0.12,
        },
        {
            "event_id": "event_002",
            "baseline_id": "tree_ring",
            "clip_score": 0.29,
            "fid": 12.4,
        },
    ]
    _write_metric_outputs(tmp_path, rows)

    report = build_pilot_metric_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "fixed_fpr_statistics_pilot"
    assert report["metric_summary"]["metric_row_count"] == 2
    assert report["metric_summary"]["advanced_metric_fields"] == ["clip_score", "fid", "lpips"]
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_metric_output_acceptance_fails_for_non_numeric_metric_value(tmp_path) -> None:
    """metric 值必须为数值, 否则不能进入论文质量表。"""
    rows = [{"event_id": "event_001", "method_name": "ceg", "psnr": "not_a_number"}]
    _write_metric_outputs(tmp_path, rows)

    report = build_pilot_metric_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "non_numeric_metric_value" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_metric_output_acceptance_requires_formal_evidence_when_requested(tmp_path) -> None:
    """启用正式证据要求时, 缺少 external evidence report 必须失败。"""
    rows = [{"event_id": "event_001", "method_name": "ceg", "psnr": 31.5}]
    _write_metric_outputs(tmp_path, rows)

    report = build_pilot_metric_output_acceptance_report(tmp_path, require_formal_evidence=True)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_required_external_evidence_report" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_metric_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "metric_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_metric_outputs.py",
            "--output-root",
            str(tmp_path / "missing_metric_root"),
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
    assert report["artifact_name"] == "pilot_metric_output_acceptance_report.json"
