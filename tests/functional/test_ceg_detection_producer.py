"""验证 CEG detection producer 把图像 manifest 转换为协议事件。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from experiments.ceg_detection_producer import build_detection_events_from_image_manifests
from main.analysis.attack_images import run_attack_workflow
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_detection_producer_builds_events_from_image_pairs_and_attacks(tmp_path) -> None:
    """image_pairs 和 attack manifest 应能生成 CEG detection events。"""
    input_root = tmp_path / "inputs"
    attack_root = tmp_path / "attack"
    detection_root = tmp_path / "detection"
    manifest = write_paper_dry_run_inputs(input_root)
    image_pairs = json.loads((input_root / manifest["image_pairs_path"]).read_text(encoding="utf-8"))
    run_attack_workflow(image_pairs[:2], attack_root, attack_families=("brightness_contrast",))
    attacked_manifest = json.loads(
        (attack_root / "image_manifests" / "attacked_image_manifest.json").read_text(encoding="utf-8")
    )

    events = build_detection_events_from_image_manifests(image_pairs[:2], attacked_manifest)

    assert len(events) == 6
    assert {event["method_name"] for event in events} == {"ceg"}
    assert "attacked_positive" in {event["sample_role"] for event in events}
    assert all("content_score_raw" in event["payload"]["content"] for event in events)

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
    producer_manifest = json.loads((detection_root / "ceg_detection_producer_manifest.json").read_text(encoding="utf-8"))
    assert producer_manifest["formal_result_claim"] is False
    assert producer_manifest["attacked_manifest_consumed"] is True
    assert (detection_root / "detection_events.json").is_file()
    assert (detection_root / "detection_thresholds.json").is_file()


@pytest.mark.quick
def test_detection_producer_outputs_feed_paper_package(tmp_path) -> None:
    """detection producer 的 events 应可进入 build_paper_outputs 和结果包。"""
    input_root = tmp_path / "inputs"
    attack_root = tmp_path / "attack"
    detection_root = tmp_path / "detection"
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
            "scripts/build_paper_outputs.py",
            "--events",
            str(detection_root / "detection_events.json"),
            "--thresholds",
            str(detection_root / "detection_thresholds.json"),
            "--baseline-observations",
            str(input_root / manifest["baseline_observations_path"]),
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
    event_records = json.loads((output_root / "event_records.json").read_text(encoding="utf-8"))

    assert any(record["sample_role"] == "attacked_positive" for record in event_records)
    assert "image_manifests/attacked_image_manifest.json" in package_manifest["copied_files"]
    assert (package_root / "artifacts" / "attack_tpr_at_fixed_fpr_table.csv").is_file()
