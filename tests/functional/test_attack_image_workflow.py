"""验证图像攻击 workflow 和 attack manifest 结果包入口。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.attack_images import run_attack_workflow
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_run_attack_workflow_writes_attack_manifests_and_pairs(tmp_path) -> None:
    """image_pairs 应能生成 attacked image manifest、attack shard manifest 和攻击后配对。"""
    input_root = tmp_path / "inputs"
    attack_root = tmp_path / "attack_outputs"
    manifest = write_paper_dry_run_inputs(input_root)
    rows = json.loads((input_root / manifest["image_pairs_path"]).read_text(encoding="utf-8"))

    shard_manifest = run_attack_workflow(rows[:1], attack_root, attack_families=("brightness_contrast", "gaussian_noise"))

    attacked_manifest = json.loads(
        (attack_root / "image_manifests" / "attacked_image_manifest.json").read_text(encoding="utf-8")
    )
    attacked_pairs = json.loads((attack_root / "image_pairs_attacked.json").read_text(encoding="utf-8"))
    assert shard_manifest["input_image_pair_count"] == 1
    assert attacked_manifest["attacked_image_count"] == 2
    assert len(attacked_pairs) == 2
    assert all(Path(row["attacked_image_path"]).is_file() for row in attacked_pairs)


@pytest.mark.quick
def test_build_paper_outputs_accepts_attack_manifests_for_formal_requirements(tmp_path) -> None:
    """正式 requirements 启用时, 一键输出应携带 attack manifest 并进入结果包。"""
    input_root = tmp_path / "inputs"
    attack_root = tmp_path / "attack_outputs"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
    manifest = write_paper_dry_run_inputs(input_root)

    subprocess.run(
        [
            sys.executable,
            "scripts/run_image_attack_workflow.py",
            "--image-pairs",
            str(input_root / manifest["image_pairs_path"]),
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
            "scripts/build_paper_outputs.py",
            "--events",
            str(input_root / manifest["events_path"]),
            "--thresholds",
            str(input_root / manifest["thresholds_path"]),
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

    assert "image_manifests/attacked_image_manifest.json" in package_manifest["copied_files"]
    assert "image_manifests/attack_shard_manifest.json" in package_manifest["copied_files"]
