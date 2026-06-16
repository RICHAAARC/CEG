"""验证论文结果 Markdown 报告导出。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.paper_report import write_paper_results_report


@pytest.mark.quick
def test_build_paper_outputs_writes_markdown_results_report(tmp_path) -> None:
    """一键输出脚本应写出 Markdown 论文结果报告和 manifest。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    input_manifest = write_paper_dry_run_inputs(input_root)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(input_root / input_manifest["events_path"]),
            "--thresholds",
            str(input_root / input_manifest["thresholds_path"]),
            "--baseline-observations",
            str(input_root / input_manifest["baseline_observations_path"]),
            "--metric-rows",
            str(input_root / input_manifest["metric_rows_path"]),
            "--out",
            str(output_root),
            "--require-paper-readiness",
        ],
        cwd=".",
        check=True,
    )

    report_text = (output_root / "paper_results_report.md").read_text(encoding="utf-8")
    manifest = json.loads((output_root / "paper_results_report_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((output_root / "paper_outputs_summary.json").read_text(encoding="utf-8"))

    assert "# CEG 论文结果包报告" in report_text
    assert "formal_main_table.csv" in report_text
    assert "detection_roc_curve.csv" in report_text
    assert "Supported claims 审计" in report_text
    assert "paper_claim_audit.json" in report_text
    assert manifest["artifact_name"] == "paper_results_report_manifest.json"
    assert summary["paper_results_report_path"] == "paper_results_report.md"
    assert summary["paper_readiness_decision"] == "pass"


@pytest.mark.quick
def test_export_paper_results_report_cli_rebuilds_report(tmp_path) -> None:
    """独立报告导出 CLI 应能从已有输出目录重新生成报告。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    input_manifest = write_paper_dry_run_inputs(input_root)
    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(input_root / input_manifest["events_path"]),
            "--thresholds",
            str(input_root / input_manifest["thresholds_path"]),
            "--baseline-observations",
            str(input_root / input_manifest["baseline_observations_path"]),
            "--metric-rows",
            str(input_root / input_manifest["metric_rows_path"]),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )
    (output_root / "paper_results_report.md").unlink()

    subprocess.run(
        [sys.executable, "scripts/export_paper_results_report.py", "--output-root", str(output_root)],
        cwd=".",
        check=True,
    )

    manifest = write_paper_results_report(output_root)
    assert (output_root / "paper_results_report.md").exists()
    assert manifest["report_path"] == "paper_results_report.md"
