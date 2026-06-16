"""验证论文结果输出包导出。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.result_package import export_paper_results_package, validate_paper_results_package


@pytest.mark.quick
def test_export_paper_results_package_collects_all_governed_outputs(tmp_path) -> None:
    """结果包应收集 records、artifacts、图表、LaTeX、PDF、报告和 claim audit。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
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

    manifest = export_paper_results_package(output_root, package_root)
    validation = validate_paper_results_package(package_root)

    assert manifest["package_status"] == "complete"
    assert manifest["readiness_decision"] == "pass"
    assert manifest["claim_audit_decision"] == "pass"
    assert "artifacts/paper_claim_audit.json" in manifest["copied_files"]
    assert "paper_results_report.md" in manifest["copied_files"]
    assert any(path.startswith("rendered_figures/figures/") and path.endswith(".svg") for path in manifest["copied_files"])
    assert "pdf_figures/paper_figures_preview.pdf" in manifest["copied_files"]
    assert validation["overall_decision"] == "pass"


@pytest.mark.quick
def test_export_paper_results_package_cli_writes_validation(tmp_path) -> None:
    """CLI 应导出结果包 manifest 并写出校验报告。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
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
        text=True,
        capture_output=True,
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/export_paper_results_package.py",
            "--source-output-root",
            str(output_root),
            "--package-root",
            str(package_root),
        ],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((package_root / "paper_results_package_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((package_root / "paper_results_package_validation.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == len(manifest["files"])
    assert validation["overall_decision"] == "pass"
