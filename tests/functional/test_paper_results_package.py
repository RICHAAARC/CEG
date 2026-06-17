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
    (output_root / "external_result_evidence_report.json").write_text(
        json.dumps(
            {
                "artifact_name": "external_result_evidence_report.json",
                "overall_decision": "pass",
                "require_formal_claim": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_root / "paper_result_evidence_report.json").write_text(
        json.dumps(
            {
                "artifact_name": "paper_result_evidence_report.json",
                "overall_decision": "pass",
                "target_kind": "paper_output_directory",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = export_paper_results_package(output_root, package_root)
    validation = validate_paper_results_package(package_root)

    assert manifest["package_status"] == "complete"
    assert manifest["readiness_decision"] == "pass"
    assert manifest["claim_audit_decision"] == "pass"
    assert "artifacts/paper_claim_audit.json" in manifest["copied_files"]
    assert "paper_results_report.md" in manifest["copied_files"]
    assert "paper_writing_index.json" in manifest["copied_files"]
    assert "paper_writing_index.md" in manifest["copied_files"]
    assert "paper_result_evidence_report.json" in manifest["copied_files"]
    assert "external_result_evidence_report.json" in manifest["copied_files"]
    assert (package_root / "paper_result_evidence_report.json").is_file()
    assert (package_root / "external_result_evidence_report.json").is_file()
    assert any(path.startswith("rendered_figures/figures/") and path.endswith(".svg") for path in manifest["copied_files"])
    assert "pdf_figures/paper_figures_preview.pdf" in manifest["copied_files"]
    writing_index = json.loads((package_root / "paper_writing_index.json").read_text(encoding="utf-8"))
    assert writing_index["summary"]["main_table_count"] >= 1
    assert writing_index["summary"]["rendered_figure_count"] >= 1
    assert writing_index["summary"]["evidence_file_count"] >= 1
    assert any(item["relative_path"] == "artifacts/formal_main_table.csv" for item in writing_index["sections"]["main_tables"])
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
    assert manifest["writing_index_files"] == ["paper_writing_index.json", "paper_writing_index.md"]
    assert (package_root / "paper_writing_index.md").is_file()
    assert validation["overall_decision"] == "pass"
