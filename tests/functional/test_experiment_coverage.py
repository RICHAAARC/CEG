"""验证论文实验矩阵覆盖率审计。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.experiment_coverage import build_experiment_coverage_report
from experiments.experiment_matrix import expand_experiment_matrix
from experiments.paper_fixture_factory import write_paper_dry_run_inputs


@pytest.mark.quick
def test_experiment_matrix_includes_main_ceg_and_ablation_names() -> None:
    """实验矩阵必须同时覆盖 CEG 主方法、内部消融和外部 baseline。"""
    cells = expand_experiment_matrix(
        {
            "profiles": ["paper_main_probe"],
            "splits": ["test"],
            "method_groups": ["ceg_main", "ceg_ablation", "external_baseline"],
            "sample_roles": ["positive_source"],
            "attack_families": ["clean"],
            "attack_levels": ["none"],
        }
    )
    method_names = {cell.method_name for cell in cells}

    assert "ceg" in method_names
    assert "ceg_full" in method_names
    assert "ceg_content_only" in method_names
    assert "tree_ring" in method_names


@pytest.mark.quick
def test_experiment_coverage_report_detects_missing_matrix_cells() -> None:
    """覆盖率报告应显式列出 records 尚未覆盖的论文矩阵组合。"""
    matrix_cells = [
        {
            "cell_id": "cell_present",
            "profile": "paper_main_probe",
            "split": "test",
            "method_group": "ceg_main",
            "method_name": "ceg",
            "sample_role": "positive_source",
            "attack_condition": "clean_none",
        },
        {
            "cell_id": "cell_missing",
            "profile": "paper_main_probe",
            "split": "test",
            "method_group": "external_baseline",
            "method_name": "tree_ring",
            "sample_role": "positive_source",
            "attack_condition": "clean_none",
        },
    ]
    records = [
        {
            "split": "test",
            "method_name": "ceg",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "attack_condition": "clean_none",
        }
    ]

    report = build_experiment_coverage_report(records, matrix_cells, profile="paper_main_probe")

    assert report["overall_decision"] == "fail"
    assert report["covered_key_count"] == 1
    assert report["missing_key_count"] == 1
    assert report["missing_examples"][0]["method_name"] == "tree_ring"


@pytest.mark.quick
def test_build_paper_outputs_writes_experiment_coverage_artifact(tmp_path) -> None:
    """一键论文输出应把实验覆盖率报告纳入 artifacts 和结果包候选。"""
    input_root = tmp_path / "inputs"
    matrix_root = tmp_path / "matrix"
    output_root = tmp_path / "paper_outputs"
    input_manifest = write_paper_dry_run_inputs(input_root)
    subprocess.run(
        [
            sys.executable,
            "scripts/build_experiment_matrix.py",
            "--config",
            "configs/paper_experiment_matrix.json",
            "--out",
            str(matrix_root),
        ],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    )
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
            "--experiment-matrix",
            str(matrix_root / "experiment_matrix.json"),
            "--out",
            str(output_root),
            "--require-paper-readiness",
        ],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    )

    report = json.loads((output_root / "artifacts" / "paper_experiment_coverage_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "artifacts" / "artifact_manifest.json").read_text(encoding="utf-8"))

    assert report["artifact_name"] == "paper_experiment_coverage_report.json"
    assert report["overall_decision"] == "fail"
    assert report["missing_key_count"] > 0
    assert "paper_experiment_coverage_report.json" in manifest["artifact_names"]
