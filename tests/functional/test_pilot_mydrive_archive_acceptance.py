"""验证 MyDrive 风格 paper_results_package 归档输出接收门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_mydrive_archive_acceptance import build_pilot_mydrive_archive_acceptance_report
from main.analysis.result_archive import archive_paper_results_package


def _write_minimal_package(root) -> None:
    """写出满足 package validation 的最小结果包。"""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "artifact_name": "paper_results_package_manifest.json",
        "package_status": "complete",
        "source_output_root": str(root),
        "copied_files": [],
        "missing_files": [],
        "file_count": 0,
        "package_digest": "empty_digest",
        "source_manifests": [],
        "readiness_decision": "pass",
        "claim_audit_decision": "pass",
        "files": [],
    }
    (root / "paper_results_package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.quick
def test_mydrive_archive_acceptance_fails_without_manifest(tmp_path) -> None:
    """没有 archive manifest 时必须失败, 避免把未归档目录当作论文交付物。"""
    report = build_pilot_mydrive_archive_acceptance_report(tmp_path / "drive")

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "archive_paper_results_package_and_fix_outputs"
    assert any(issue["issue_type"] == "unreadable_or_missing_archive_manifest" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_mydrive_archive_acceptance_passes_archive_contract(tmp_path) -> None:
    """已归档的 snapshot、zip 和 manifest 一致时应通过接收门禁。"""
    package_root = tmp_path / "paper_results_package"
    drive_root = tmp_path / "MyDrive" / "CEG"
    _write_minimal_package(package_root)
    archive_paper_results_package(package_root, drive_root, run_id="unit_run")

    report = build_pilot_mydrive_archive_acceptance_report(drive_root, run_id="unit_run")

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "paper_writing_ready_pilot"
    assert report["summary"]["package_validation_decision"] == "pass"
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_mydrive_archive_acceptance_fails_when_zip_is_tampered(tmp_path) -> None:
    """zip 被篡改后 SHA-256 摘要不一致, 门禁必须失败。"""
    package_root = tmp_path / "paper_results_package"
    drive_root = tmp_path / "MyDrive" / "CEG"
    _write_minimal_package(package_root)
    manifest = archive_paper_results_package(package_root, drive_root, run_id="tampered_run")
    archive_path = drive_root / "package_archives" / "paper_results_package_tampered_run.zip"
    archive_path.write_bytes(archive_path.read_bytes() + b"tamper")

    report = build_pilot_mydrive_archive_acceptance_report(drive_root, manifest_path=manifest["manifest_path"])

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "archive_sha256_mismatch" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_mydrive_archive_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "mydrive_archive_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_mydrive_archive.py",
            "--drive-root",
            str(tmp_path / "missing_drive"),
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
    assert report["artifact_name"] == "pilot_mydrive_archive_acceptance_report.json"
