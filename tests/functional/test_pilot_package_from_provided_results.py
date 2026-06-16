"""验证已提供产物可以一键构建 pilot 论文结果包."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs


@pytest.mark.quick
def test_build_pilot_package_from_provided_results_archives_to_drive(tmp_path) -> None:
    """pilot package CLI 应串联 paper outputs、result package 和 Drive 归档."""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "pilot_package"
    drive_root = tmp_path / "drive" / "CEG"
    input_manifest = write_paper_dry_run_inputs(input_root)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_package_from_provided_results.py",
            "--events",
            str(input_root / input_manifest["events_path"]),
            "--thresholds",
            str(input_root / input_manifest["thresholds_path"]),
            "--baseline-observations",
            str(input_root / input_manifest["baseline_observations_path"]),
            "--metric-rows",
            str(input_root / input_manifest["metric_rows_path"]),
            "--image-pairs",
            str(input_root / input_manifest["image_pairs_path"]),
            "--out",
            str(output_root),
            "--require-paper-readiness",
            "--drive-root",
            str(drive_root),
            "--run-id",
            "pilot_cli",
            "--write-paper-result-evidence-report",
            "--allow-dry-run-paper-result-evidence",
            "--allow-missing-experiment-coverage",
        ],
        cwd=".",
        check=True,
    )

    manifest = json.loads((output_root / "pilot_package_build_manifest.json").read_text(encoding="utf-8"))
    package_validation = json.loads(
        (output_root / "paper_results_package" / "paper_results_package_validation.json").read_text(encoding="utf-8")
    )
    package_manifest = json.loads(
        (output_root / "paper_results_package" / "paper_results_package_manifest.json").read_text(encoding="utf-8")
    )
    evidence_report = json.loads(
        (output_root / "paper_results_package" / "paper_result_evidence_report.json").read_text(encoding="utf-8")
    )
    archive_manifest = json.loads(
        (drive_root / "package_manifests" / "paper_results_package_archive_manifest_pilot_cli.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["overall_decision"] == "pass"
    assert manifest["paper_result_evidence_report_path"].endswith("paper_result_evidence_report.json")
    assert "paper_result_evidence_report.json" in package_manifest["copied_files"]
    assert evidence_report["artifact_name"] == "paper_result_evidence_report.json"
    assert package_validation["overall_decision"] == "pass"
    assert archive_manifest["package_validation_decision"] == "pass"
    assert (drive_root / "package_archives" / "paper_results_package_pilot_cli.zip").is_file()


@pytest.mark.quick
def test_build_pilot_rehearsal_package_cli_writes_package_and_archive(tmp_path) -> None:
    """pilot rehearsal CLI 应能一键验证输入物化、证据报告、结果包和 Drive 归档链路。"""
    output_root = tmp_path / "pilot_rehearsal"
    drive_root = tmp_path / "drive" / "CEG"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_rehearsal_package.py",
            "--out",
            str(output_root),
            "--drive-root",
            str(drive_root),
            "--run-id",
            "rehearsal_cli",
        ],
        cwd=".",
        check=True,
    )

    rehearsal_manifest = json.loads((output_root / "pilot_rehearsal_manifest.json").read_text(encoding="utf-8"))
    pilot_input_manifest_path = output_root / "materialized_pilot_inputs" / "pilot_input_manifest.json"
    pilot_input_manifest = json.loads(pilot_input_manifest_path.read_text(encoding="utf-8"))
    package_manifest = json.loads(
        (
            output_root
            / "pilot_package"
            / "paper_results_package"
            / "paper_results_package_manifest.json"
        ).read_text(encoding="utf-8")
    )
    gap_report_path = output_root / "pilot_input_gap_report.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/analyze_pilot_input_gap.py",
            "--manifest",
            str(pilot_input_manifest_path),
            "--out",
            str(gap_report_path),
        ],
        cwd=".",
        check=True,
    )
    gap_report = json.loads(gap_report_path.read_text(encoding="utf-8"))

    assert rehearsal_manifest["overall_decision"] == "pass"
    assert rehearsal_manifest["rehearsal_scope"] == "dry_run_contract_rehearsal_not_formal_paper_result"
    assert pilot_input_manifest["detection_execution_manifest"] == "ceg_detection/ceg_detection_execution_manifest.json"
    assert pilot_input_manifest["experiment_matrix"] == "plans/paper_experiment_matrix.json"
    assert gap_report["overall_decision"] == "pass"
    assert "detection_execution_manifest" not in gap_report["missing_core_fields"]
    assert "experiment_matrix" not in gap_report["missing_core_fields"]
    assert "paper_result_evidence_report.json" in package_manifest["copied_files"]
    assert "external_result_evidence_report.json" in package_manifest["copied_files"]
    assert (drive_root / "package_archives" / "paper_results_package_rehearsal_cli.zip").is_file()
