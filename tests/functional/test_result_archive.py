"""验证论文结果包可以归档到 Drive 风格的分类目录."""

from __future__ import annotations

import json
import subprocess
import sys
from zipfile import ZipFile

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.result_archive import archive_paper_results_package
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_archive_paper_results_package_writes_drive_style_outputs(tmp_path) -> None:
    """结果包归档应同时写出目录快照、zip 包和归档 manifest."""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
    drive_root = tmp_path / "MyDrive" / "CEG"
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
    export_paper_results_package(output_root, package_root)

    manifest = archive_paper_results_package(package_root, drive_root, run_id="unit_run")

    assert manifest["package_validation_decision"] == "pass"
    assert (drive_root / "package_snapshots" / "unit_run" / "paper_results_package" / "paper_results_package_manifest.json").is_file()
    assert (drive_root / "package_archives" / "paper_results_package_unit_run.zip").is_file()
    assert (drive_root / "package_manifests" / "paper_results_package_archive_manifest_unit_run.json").is_file()
    with ZipFile(drive_root / "package_archives" / "paper_results_package_unit_run.zip") as handle:
        assert "paper_results_package_manifest.json" in handle.namelist()


@pytest.mark.quick
def test_archive_paper_results_to_drive_cli_writes_manifest(tmp_path) -> None:
    """归档 CLI 应输出与函数一致的 Drive 分类目录结构."""
    package_root = tmp_path / "paper_results_package"
    drive_root = tmp_path / "drive" / "CEG"
    package_root.mkdir()
    package_manifest = {
        "artifact_name": "paper_results_package_manifest.json",
        "package_status": "complete",
        "copied_files": [],
        "missing_files": [],
        "file_count": 0,
        "package_digest": "empty_digest",
        "readiness_decision": "pass",
        "claim_audit_decision": "pass",
        "files": [],
    }
    (package_root / "paper_results_package_manifest.json").write_text(
        json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/archive_paper_results_to_drive.py",
            "--package-root",
            str(package_root),
            "--drive-root",
            str(drive_root),
            "--run-id",
            "cli_run",
        ],
        cwd=".",
        check=True,
    )

    manifest = json.loads(
        (drive_root / "package_manifests" / "paper_results_package_archive_manifest_cli_run.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["run_id"] == "cli_run"
    assert manifest["package_validation_decision"] == "pass"
