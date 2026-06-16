"""验证 pilot 输入 manifest 的预检和一键结果包构建入口."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from experiments.pilot_input_manifest import validate_pilot_input_manifest


def _write_pilot_input_manifest(input_root):
    """基于 dry-run fixture 写出可通过预检的 pilot 输入 manifest."""
    input_manifest = write_paper_dry_run_inputs(input_root)
    pilot_manifest = {
        "artifact_name": "pilot_input_manifest.json",
        "events": input_manifest["events_path"],
        "thresholds": input_manifest["thresholds_path"],
        "baseline_observations": input_manifest["baseline_observations_path"],
        "metric_rows": input_manifest["metric_rows_path"],
        "image_pairs": input_manifest["image_pairs_path"],
    }
    manifest_path = input_root / "pilot_input_manifest.json"
    manifest_path.write_text(json.dumps(pilot_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, input_manifest


@pytest.mark.quick
def test_validate_pilot_input_manifest_accepts_fixture_paths(tmp_path) -> None:
    """pilot input preflight 应校验必需输入并解析相对路径."""
    manifest_path, _ = _write_pilot_input_manifest(tmp_path / "inputs")

    report = validate_pilot_input_manifest(manifest_path)

    assert report["overall_decision"] == "pass"
    assert report["summary"]["fail_count"] == 0
    assert report["resolved_inputs"]["events"].endswith("events.json")
    assert report["resolved_inputs"]["thresholds"].endswith("thresholds.json")
    assert any(check["field"] == "baseline_observations" and check["status"] == "pass" for check in report["checks"])
    assert any(check["field"] == "metric_rows" and check["status"] == "pass" for check in report["checks"])


@pytest.mark.quick
def test_validate_pilot_input_manifest_cli_writes_report(tmp_path) -> None:
    """校验 CLI 应能写出 preflight 报告并在 require-pass 下成功退出."""
    manifest_path, _ = _write_pilot_input_manifest(tmp_path / "inputs")
    report_path = tmp_path / "reports" / "pilot_input_manifest_validation.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_input_manifest.py",
            "--manifest",
            str(manifest_path),
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["artifact_name"] == "pilot_input_manifest_validation.json"


@pytest.mark.quick
def test_build_pilot_package_from_pilot_input_manifest(tmp_path) -> None:
    """一键构建脚本应能从 pilot_input_manifest.json 自动补齐输入路径."""
    manifest_path, _ = _write_pilot_input_manifest(tmp_path / "inputs")
    output_root = tmp_path / "pilot_package"
    drive_root = tmp_path / "drive" / "CEG"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_package_from_provided_results.py",
            "--pilot-input-manifest",
            str(manifest_path),
            "--out",
            str(output_root),
            "--require-paper-readiness",
            "--drive-root",
            str(drive_root),
            "--run-id",
            "pilot_manifest_cli",
        ],
        cwd=".",
        check=True,
    )

    build_manifest = json.loads((output_root / "pilot_package_build_manifest.json").read_text(encoding="utf-8"))
    preflight_report = json.loads((output_root / "pilot_input_manifest_validation.json").read_text(encoding="utf-8"))
    assert build_manifest["overall_decision"] == "pass"
    assert build_manifest["pilot_input_manifest"] == str(manifest_path)
    assert build_manifest["pilot_input_manifest_validation"]["overall_decision"] == "pass"
    assert preflight_report["overall_decision"] == "pass"
    assert (drive_root / "package_archives" / "paper_results_package_pilot_manifest_cli.zip").is_file()
