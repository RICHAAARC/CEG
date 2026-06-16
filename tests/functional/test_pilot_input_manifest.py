"""验证 pilot 输入 manifest 的预检和一键结果包构建入口."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from experiments.pilot_input_manifest import validate_pilot_input_manifest
from experiments.pilot_input_materializer import materialize_pilot_input_bundle


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


@pytest.mark.quick
def test_materialize_pilot_input_bundle_writes_canonical_manifest(tmp_path) -> None:
    """物化器应把已提供产物复制到 canonical 输入目录并生成可预检的 manifest."""
    source_root = tmp_path / "source_inputs"
    input_manifest = write_paper_dry_run_inputs(source_root)
    materialized_root = tmp_path / "materialized_pilot_inputs"

    materialization = materialize_pilot_input_bundle(
        materialized_root,
        events=source_root / input_manifest["events_path"],
        thresholds=source_root / input_manifest["thresholds_path"],
        baseline_observations=source_root / input_manifest["baseline_observations_path"],
        metric_rows=source_root / input_manifest["metric_rows_path"],
        image_pairs=source_root / input_manifest["image_pairs_path"],
        readiness_requirements="configs/paper_output_requirements.json",
        run_id="materialized_fixture",
    )

    pilot_manifest = json.loads((materialized_root / "pilot_input_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((materialized_root / "pilot_input_manifest_validation.json").read_text(encoding="utf-8"))
    assert materialization["overall_decision"] == "pass"
    assert pilot_manifest["events"] == "ceg_detection/detection_events.json"
    assert pilot_manifest["thresholds"] == "ceg_detection/detection_thresholds.json"
    assert pilot_manifest["baseline_observations"] == "external_baselines/baseline_observations.json"
    assert pilot_manifest["metric_rows"] == "external_metrics/metric_rows.json"
    assert pilot_manifest["image_pairs"] == "inputs/image_pairs.json"
    assert validation["overall_decision"] == "pass"
    assert (materialized_root / "ceg_detection" / "detection_events.json").is_file()
    assert (materialized_root / "configs" / "paper_output_requirements.json").is_file()


@pytest.mark.quick
def test_materialize_pilot_input_manifest_cli_can_feed_package_builder(tmp_path) -> None:
    """物化 CLI 生成的 manifest 应可直接交给一键结果包构建脚本."""
    source_root = tmp_path / "source_inputs"
    input_manifest = write_paper_dry_run_inputs(source_root)
    attack_root = tmp_path / "attack_outputs"
    materialized_root = tmp_path / "materialized_pilot_inputs"
    output_root = tmp_path / "pilot_package"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_image_attack_workflow.py",
            "--image-pairs",
            str(source_root / input_manifest["image_pairs_path"]),
            "--out",
            str(attack_root),
            "--attack-families",
            "brightness_contrast",
        ],
        cwd=".",
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/materialize_pilot_input_manifest.py",
            "--out",
            str(materialized_root),
            "--run-id",
            "materialized_cli",
            "--events",
            str(source_root / input_manifest["events_path"]),
            "--thresholds",
            str(source_root / input_manifest["thresholds_path"]),
            "--baseline-observations",
            str(source_root / input_manifest["baseline_observations_path"]),
            "--metric-rows",
            str(source_root / input_manifest["metric_rows_path"]),
            "--image-pairs",
            str(source_root / input_manifest["image_pairs_path"]),
            "--attacked-image-manifest",
            str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
            "--attack-shard-manifest",
            str(attack_root / "image_manifests" / "attack_shard_manifest.json"),
            "--readiness-requirements",
            "configs/paper_output_requirements.json",
            "--require-pass",
        ],
        cwd=".",
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_package_from_provided_results.py",
            "--pilot-input-manifest",
            str(materialized_root / "pilot_input_manifest.json"),
            "--out",
            str(output_root),
            "--require-paper-readiness",
        ],
        cwd=".",
        check=True,
    )

    build_manifest = json.loads((output_root / "pilot_package_build_manifest.json").read_text(encoding="utf-8"))
    assert build_manifest["overall_decision"] == "pass"
    assert build_manifest["pilot_input_manifest_validation"]["overall_decision"] == "pass"
    assert (output_root / "paper_results_package" / "paper_results_package_manifest.json").is_file()


@pytest.mark.quick
def test_build_pilot_package_from_raw_inputs_cli_materializes_builds_and_archives(tmp_path) -> None:
    """分散输入一键入口应完成物化、结果包构建和 Drive 分类归档."""
    source_root = tmp_path / "source_inputs"
    input_manifest = write_paper_dry_run_inputs(source_root)
    attack_root = tmp_path / "attack_outputs"
    materialized_root = tmp_path / "materialized_pilot_inputs"
    output_root = tmp_path / "pilot_package"
    drive_root = tmp_path / "drive" / "CEG"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_image_attack_workflow.py",
            "--image-pairs",
            str(source_root / input_manifest["image_pairs_path"]),
            "--out",
            str(attack_root),
            "--attack-families",
            "brightness_contrast",
        ],
        cwd=".",
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_package_from_raw_inputs.py",
            "--materialized-input-root",
            str(materialized_root),
            "--out",
            str(output_root),
            "--run-id",
            "raw_inputs_cli",
            "--events",
            str(source_root / input_manifest["events_path"]),
            "--thresholds",
            str(source_root / input_manifest["thresholds_path"]),
            "--baseline-observations",
            str(source_root / input_manifest["baseline_observations_path"]),
            "--metric-rows",
            str(source_root / input_manifest["metric_rows_path"]),
            "--image-pairs",
            str(source_root / input_manifest["image_pairs_path"]),
            "--attacked-image-manifest",
            str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
            "--attack-shard-manifest",
            str(attack_root / "image_manifests" / "attack_shard_manifest.json"),
            "--readiness-requirements",
            "configs/paper_output_requirements.json",
            "--require-paper-readiness",
            "--drive-root",
            str(drive_root),
        ],
        cwd=".",
        check=True,
    )

    raw_manifest = json.loads((output_root / "pilot_raw_input_package_build_manifest.json").read_text(encoding="utf-8"))
    build_manifest = json.loads((output_root / "pilot_package_build_manifest.json").read_text(encoding="utf-8"))
    assert raw_manifest["overall_decision"] == "pass"
    assert raw_manifest["materialization"]["overall_decision"] == "pass"
    assert build_manifest["overall_decision"] == "pass"
    assert (materialized_root / "pilot_input_manifest.json").is_file()
    assert (drive_root / "package_archives" / "paper_results_package_raw_inputs_cli.zip").is_file()
