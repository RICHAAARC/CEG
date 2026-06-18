"""验证 external baseline pilot producer 接入论文结果包链路。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.baseline_pilot_producer import build_baseline_pilot_observations
from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.attack_images import run_attack_workflow
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_baseline_pilot_producer_builds_registered_baseline_rows(tmp_path) -> None:
    """pilot producer 应为每个 detection event 生成全部外部 baseline observation。"""
    events = [
        {
            "event_id": "positive_001",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": True,
            "payload": {},
        },
        {
            "event_id": "negative_001",
            "split": "test",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "payload": {},
        },
    ]

    rows = build_baseline_pilot_observations(events)

    assert len(rows) == 8
    assert {row["baseline_id"] for row in rows} == {
        "tree_ring",
        "gaussian_shading",
        "shallow_diffuse",
        "t2smark",
    }
    assert all(row["formal_result_claim"] is False for row in rows)
    assert all(row["threshold"] == 0.5 for row in rows)


@pytest.mark.quick
def test_baseline_pilot_outputs_feed_paper_package(tmp_path) -> None:
    """baseline pilot 产物应能进入 build_paper_outputs 和 paper_results_package。"""
    input_root = tmp_path / "inputs"
    attack_root = tmp_path / "attack"
    detection_root = tmp_path / "detection"
    baseline_root = tmp_path / "external_baselines"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
    manifest = write_paper_dry_run_inputs(input_root)
    image_pairs = json.loads((input_root / manifest["image_pairs_path"]).read_text(encoding="utf-8"))
    run_attack_workflow(image_pairs, attack_root, attack_families=("brightness_contrast",))

    subprocess.run(
        [
            sys.executable,
            "scripts/run_ceg_detection_producer.py",
            "--image-pairs",
            str(input_root / manifest["image_pairs_path"]),
            "--attacked-image-manifest",
            str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
            "--out",
            str(detection_root),
        ],
        cwd=".",
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/run_baseline_pilot_producer.py",
            "--events",
            str(detection_root / "detection_events.json"),
            "--out",
            str(baseline_root),
        ],
        cwd=".",
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(detection_root / "detection_events.json"),
            "--thresholds",
            str(detection_root / "detection_thresholds.json"),
            "--baseline-observations",
            str(baseline_root / "baseline_observations.json"),
            "--baseline-execution-manifest",
            str(baseline_root / "baseline_execution_manifest.json"),
            "--metric-rows",
            str(input_root / manifest["metric_rows_path"]),
            "--image-pairs",
            str(input_root / manifest["image_pairs_path"]),
            "--attacked-image-manifest",
            str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
            "--attack-shard-manifest",
            str(attack_root / "image_manifests" / "attack_shard_manifest.json"),
            "--readiness-requirements",
            "configs/paper_output_requirements.json",
            "--out",
            str(output_root),
            "--require-paper-readiness",
        ],
        cwd=".",
        check=True,
    )
    package_manifest = export_paper_results_package(output_root, package_root)
    baseline_manifest = json.loads((output_root / "baseline_results" / "baseline_execution_manifest.json").read_text(encoding="utf-8"))

    assert baseline_manifest["formal_result_claim"] is False
    assert baseline_manifest["baseline_ids"] == [
        "gaussian_shading",
        "shallow_diffuse",
        "t2smark",
        "tree_ring",
    ]
    assert "baseline_results/baseline_execution_manifest.json" in package_manifest["copied_files"]
    assert "baseline_results/baseline_observations.json" in package_manifest["copied_files"]
    assert (package_root / "artifacts" / "baseline_comparison_table.csv").is_file()
