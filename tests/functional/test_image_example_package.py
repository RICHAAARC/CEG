"""验证图像 manifest 和论文示例图结果包。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.image_examples import export_image_example_package
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_export_image_example_package_writes_manifests_and_examples(tmp_path) -> None:
    """image_pairs 应能导出 image_manifests 和 image_examples。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    manifest = write_paper_dry_run_inputs(input_root)
    rows = json.loads((input_root / manifest["image_pairs_path"]).read_text(encoding="utf-8"))

    example_manifest = export_image_example_package(rows, output_root, max_examples_per_role=1)

    assert example_manifest["example_count"] == 3
    assert (output_root / "image_manifests" / "image_generation_manifest.json").is_file()
    assert (output_root / "image_manifests" / "image_pair_manifest.json").is_file()
    assert (output_root / "image_examples" / "image_example_manifest.json").is_file()
    assert (output_root / "image_examples" / "clean").is_dir()
    assert (output_root / "image_examples" / "watermarked").is_dir()
    assert (output_root / "image_examples" / "attacked").is_dir()


@pytest.mark.quick
def test_build_paper_outputs_with_image_pairs_exports_image_examples_and_package(tmp_path) -> None:
    """一键论文输出应能把图像 manifest 和示例图带入 paper_results_package。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    package_root = tmp_path / "paper_results_package"
    manifest = write_paper_dry_run_inputs(input_root)

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

    assert (output_root / "paper_readiness_report.json").is_file()
    assert (package_root / "image_manifests" / "image_generation_manifest.json").is_file()
    assert (package_root / "image_manifests" / "image_pair_manifest.json").is_file()
    assert (package_root / "image_examples" / "image_example_manifest.json").is_file()
    assert any(path.startswith("image_examples/clean/") for path in package_manifest["copied_files"])
