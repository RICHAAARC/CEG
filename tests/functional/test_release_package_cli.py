"""验证发布包构建 CLI。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.quick
def test_build_release_package_materializes_minimal_method_package(tmp_path) -> None:
    """发布包 CLI 应生成非 dry-run 的 minimal_method_package。"""
    output_root = tmp_path / "minimal_release"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_release_package.py",
            "--profile",
            "minimal_method_package",
            "--root",
            ".",
            "--output",
            str(output_root),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((output_root / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest["release_package_status"] == "materialized"
    assert "main/methods/ceg/decision.py" in manifest["copied_files"]
    assert not (output_root / "tools").exists()
    assert "minimal_method_package" in completed.stdout


@pytest.mark.quick
def test_paper_artifact_rebuild_package_runs_protocol_cli(tmp_path) -> None:
    """paper_artifact_rebuild_package 应能独立运行协议 CLI 并重建产物。"""
    package_root = tmp_path / "artifact_package"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_release_package.py",
            "--profile",
            "paper_artifact_rebuild_package",
            "--root",
            ".",
            "--output",
            str(package_root),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    events_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "event_pkg",
                    "split": "test",
                    "sample_role": "positive_source",
                    "attack_family": "rotate",
                    "attack_condition": "rotate_light",
                    "is_watermarked": True,
                    "payload": {
                        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                        "content": {
                            "content_score_raw": 0.49,
                            "content_score_aligned": 0.52,
                            "content_fail_reason": "geometry_suspected",
                        },
                        "geometry": {
                            "registration_confidence": 0.9,
                            "anchor_inlier_ratio": 0.8,
                            "recovered_sync_consistency": 0.85,
                        },
                        "attestation": {"attestation_score": 0.8},
                        "baseline_observations": [
                            {"baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5}
                        ],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    thresholds_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")
    output_root = tmp_path / "protocol_output"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "main.cli.run_paper_protocol",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--profile",
            "paper_main_probe",
            "--out",
            str(output_root),
        ],
        cwd=package_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert (output_root / "event_records.json").exists()
    assert (output_root / "artifacts" / "formal_main_table.csv").exists()
    assert (output_root / "artifacts" / "baseline_comparison_table.csv").exists()


@pytest.mark.quick
def test_paper_artifact_rebuild_package_includes_colab_acceptance_cli(tmp_path) -> None:
    """paper_artifact_rebuild_package 应包含 Colab 最终验收 CLI, 使下载后的 bundle 可离线复核。"""
    package_root = tmp_path / "artifact_package"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_release_package.py",
            "--profile",
            "paper_artifact_rebuild_package",
            "--root",
            ".",
            "--output",
            str(package_root),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((package_root / "release_manifest.json").read_text(encoding="utf-8"))
    assert "scripts/run_colab_acceptance_checks.py" in manifest["copied_files"]
    completed = subprocess.run(
        [sys.executable, "scripts/run_colab_acceptance_checks.py", "--help"],
        cwd=package_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "--bundle" in completed.stdout
    assert "--require-external-command-results" in completed.stdout
