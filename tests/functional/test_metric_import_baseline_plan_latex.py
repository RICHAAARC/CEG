"""验证高级指标导入、baseline 命令计划和 LaTeX 表格导出。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.baseline_plan import build_baseline_plan_manifest, load_baseline_command_plan
from experiments.metric_file_adapter import build_metric_row_import_manifest, load_metric_rows, merge_metric_rows_into_records
from main.analysis.latex_tables import build_latex_tables_from_artifacts, write_latex_tables
from main.analysis.result_package import export_paper_results_package


@pytest.mark.quick
def test_metric_rows_merge_external_lpips_fid_clip_score(tmp_path) -> None:
    """外部高级指标文件应能按 event_id + method_name 合并进 records。"""
    metric_path = tmp_path / "advanced_metrics.json"
    metric_path.write_text(
        json.dumps(
            [
                {"event_id": "e1", "method_name": "ceg", "lpips": 0.04, "fid": 8.5, "clip_score": 0.31},
                {"event_id": "e1", "baseline_id": "tree_ring", "lpips": "0.06", "fid": "9.2"},
            ]
        ),
        encoding="utf-8",
    )

    rows = load_metric_rows(metric_path)
    merged = merge_metric_rows_into_records(
        [
            {"event_id": "e1", "method_name": "ceg", "final_decision": True},
            {"event_id": "e1", "method_name": "tree_ring", "final_decision": True},
        ],
        rows,
    )

    assert merged[0]["lpips"] == pytest.approx(0.04)
    assert merged[0]["fid"] == pytest.approx(8.5)
    assert merged[0]["clip_score"] == pytest.approx(0.31)
    assert merged[1]["lpips"] == pytest.approx(0.06)
    assert merged[1]["fid"] == pytest.approx(9.2)


@pytest.mark.quick
def test_baseline_command_plan_loads_and_manifests_commands(tmp_path) -> None:
    """baseline 命令计划应规范化 baseline id 并保留显式命令列表。"""
    plan_path = tmp_path / "baseline_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "baseline_id": "Tree-Ring",
                    "command": [sys.executable, "-c", "print('baseline')"],
                    "output_path": str(tmp_path / "tree_ring.json"),
                    "timeout_seconds": 30,
                }
            ]
        ),
        encoding="utf-8",
    )

    specs = load_baseline_command_plan(plan_path)
    manifest = build_baseline_plan_manifest(specs)

    assert specs[0].baseline_id == "tree_ring"
    assert specs[0].command[0] == sys.executable
    assert manifest["baseline_count"] == 1
    assert manifest["baselines"][0]["baseline_id"] == "tree_ring"


@pytest.mark.quick
def test_run_baseline_plan_cli_collects_observations(tmp_path) -> None:
    """baseline plan CLI 应执行命令并汇总 observation 输出。"""
    observation_path = tmp_path / "tree_ring_observations.json"
    code = (
        "import json, pathlib; "
        f"pathlib.Path(r'{observation_path}').write_text(json.dumps([{{'event_id':'e1','baseline_id':'tree_ring','score':0.8,'threshold':0.5}}]), encoding='utf-8')"
    )
    plan_path = tmp_path / "baseline_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "baseline_id": "tree_ring",
                    "command": [sys.executable, "-c", code],
                    "output_path": str(observation_path),
                    "timeout_seconds": 30,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "baseline_outputs"

    subprocess.run(
        [sys.executable, "scripts/run_baseline_plan.py", "--plan", str(plan_path), "--out", str(output_root)],
        cwd=".",
        check=True,
    )

    rows = json.loads((output_root / "baseline_observations.json").read_text(encoding="utf-8"))
    assert rows[0]["baseline_id"] == "tree_ring"
    assert (output_root / "baseline_command_results.json").exists()
    assert (output_root / "baseline_execution_manifest.json").exists()


@pytest.mark.quick
def test_run_metric_plan_cli_collects_rows_and_execution_manifest(tmp_path) -> None:
    """metric plan CLI 应写出 metric rows、命令结果和执行 manifest。"""
    metric_path = tmp_path / "lpips_rows.json"
    code = (
        "import json, pathlib; "
        f"pathlib.Path(r'{metric_path}').write_text(json.dumps([{{'event_id':'e1','method_name':'ceg','lpips':0.04}}]), encoding='utf-8')"
    )
    plan_path = tmp_path / "metric_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "metric_name": "lpips",
                    "command": [sys.executable, "-c", code],
                    "output_path": str(metric_path),
                    "timeout_seconds": 30,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "metric_outputs"

    subprocess.run(
        [sys.executable, "scripts/run_metric_plan.py", "--plan", str(plan_path), "--out", str(output_root)],
        cwd=".",
        check=True,
    )

    rows = json.loads((output_root / "metric_rows.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "metric_execution_manifest.json").read_text(encoding="utf-8"))
    assert rows[0]["lpips"] == pytest.approx(0.04)
    assert manifest["artifact_name"] == "metric_execution_manifest.json"
    assert manifest["metric_names"] == ["lpips"]


@pytest.mark.quick
def test_metric_row_import_manifest_requires_formal_evidence(tmp_path) -> None:
    """正式离线高级指标导入必须显式绑定外部运行证据."""
    rows = [{"event_id": "e1", "method_name": "ceg", "lpips": 0.04, "fid": 8.5, "clip_score": 0.31}]

    with pytest.raises(ValueError, match="formal metric import requires"):
        build_metric_row_import_manifest(
            rows,
            source_metric_rows_path=tmp_path / "source_metrics.json",
            output_metric_rows_path=tmp_path / "metric_rows.json",
            formal_result_claim=True,
        )


@pytest.mark.quick
def test_import_metric_rows_cli_writes_package_ready_manifest(tmp_path) -> None:
    """离线高级指标 rows 导入应写出 build_paper_outputs 可直接消费的文件."""
    source_path = tmp_path / "offline_metric_rows.json"
    output_root = tmp_path / "metric_results"
    source_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "e1",
                    "method_name": "ceg",
                    "lpips": 0.04,
                    "fid": 8.5,
                    "clip_score": 0.31,
                }
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/import_metric_rows.py",
            "--metric-rows",
            str(source_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )

    rows = json.loads((output_root / "metric_rows.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "metric_execution_manifest.json").read_text(encoding="utf-8"))
    assert rows[0]["lpips"] == pytest.approx(0.04)
    assert manifest["producer_role"] == "offline_external_metric_row_import"
    assert manifest["formal_result_claim"] is False
    assert manifest["advanced_metric_fields"] == ["clip_score", "fid", "lpips"]


@pytest.mark.quick
def test_latex_tables_are_generated_from_artifact_tables(tmp_path) -> None:
    """LaTeX 表格导出器应从内存 artifacts 写出 tex 文件和 manifest。"""
    artifacts = {
        "formal_main_table.csv": [
            {"method_name": "ceg", "tpr": 1.0, "clean_fpr": 0.0},
            {"method_name": "tree_ring", "tpr": 0.8, "clean_fpr": 0.1},
        ],
        "bit_recovery_metrics.csv": [{"method_name": "ceg", "bit_accuracy": 0.95}],
    }

    latex_tables = build_latex_tables_from_artifacts(artifacts)
    manifest = write_latex_tables(tmp_path, artifacts)

    assert "formal_main_table.tex" in latex_tables
    assert "\\begin{table}" in latex_tables["formal_main_table.tex"]
    assert (tmp_path / "formal_main_table.tex").exists()
    assert manifest["table_count"] == 2


@pytest.mark.quick
def test_build_paper_outputs_cli_merges_metric_rows_and_exports_latex(tmp_path) -> None:
    """一键论文输出脚本应合并高级指标并导出 LaTeX 表格。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    metrics_path = tmp_path / "metrics.json"
    output_root = tmp_path / "paper_outputs"
    events_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "event_metric_merge",
                    "split": "test",
                    "sample_role": "positive_source",
                    "attack_family": "crop",
                    "attack_condition": "crop_light",
                    "is_watermarked": True,
                    "payload": {
                        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                        "content": {"content_score_raw": 0.8},
                        "geometry": {
                            "registration_confidence": 0.9,
                            "anchor_inlier_ratio": 0.8,
                            "recovered_sync_consistency": 0.8,
                        },
                        "attestation": {"attestation_score": 0.9},
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    thresholds_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")
    metrics_path.write_text(
        json.dumps([{"event_id": "event_metric_merge", "method_name": "ceg", "lpips": 0.03, "fid": 7.5}]),
        encoding="utf-8",
    )

    metric_manifest_path = tmp_path / "metric_execution_manifest.json"
    metric_manifest_path.write_text(
        json.dumps(
            {
                "artifact_name": "metric_execution_manifest.json",
                "producer_id": "test_metric_source",
                "formal_result_claim": False,
                "metric_rows_path": str(metrics_path),
                "metric_row_count": 1,
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--metric-rows",
            str(metrics_path),
            "--metric-execution-manifest",
            str(metric_manifest_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )

    records = json.loads((output_root / "event_records.json").read_text(encoding="utf-8"))
    assert records[0]["lpips"] == pytest.approx(0.03)
    assert records[0]["fid"] == pytest.approx(7.5)
    assert (output_root / "latex_tables" / "formal_main_table.tex").exists()
    summary = json.loads((output_root / "paper_outputs_summary.json").read_text(encoding="utf-8"))
    assert summary["latex_table_count"] >= 1
    assert summary["metric_execution_manifest_path"] == "metric_results/metric_execution_manifest.json"
    package_root = tmp_path / "paper_results_package"
    package_manifest = export_paper_results_package(output_root, package_root, require_readiness=False)
    assert "metric_results/metric_rows.json" in package_manifest["copied_files"]
    assert "metric_results/metric_execution_manifest.json" in package_manifest["copied_files"]
