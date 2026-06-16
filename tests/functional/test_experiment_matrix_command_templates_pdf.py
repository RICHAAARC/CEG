"""验证实验矩阵、命令模板、高级指标计划和 PDF 图表导出。"""

from __future__ import annotations

import json
import subprocess
import sys

from experiments.command_templates import materialize_baseline_command_plan, materialize_metric_command_plan
from experiments.experiment_matrix import expand_experiment_matrix, write_experiment_matrix
from experiments.metric_plan import build_metric_plan_manifest, load_metric_command_plan
from main.analysis.pdf_figures import render_figure_specs_pdf_package


def test_experiment_matrix_expands_required_method_and_attack_axes(tmp_path) -> None:
    """实验矩阵应同时覆盖 CEG 消融、外部 baseline 和攻击强度。"""
    cells = expand_experiment_matrix(
        {
            "profiles": ["paper_main_probe"],
            "splits": ["test"],
            "method_groups": ["ceg_ablation", "external_baseline"],
            "sample_roles": ["positive_source"],
            "attack_families": ["clean", "crop"],
            "attack_levels": ["none", "light"],
        }
    )
    manifest = write_experiment_matrix(tmp_path, cells)

    method_groups = {cell.method_group for cell in cells}
    method_names = {cell.method_name for cell in cells}
    attack_conditions = {cell.attack_condition for cell in cells}
    assert method_groups == {"ceg_ablation", "external_baseline"}
    assert "ceg_Full" in method_names
    assert "tree_ring" in method_names
    assert attack_conditions == {"clean_none", "crop_light"}
    assert manifest["cell_count"] == len(cells)
    assert (tmp_path / "experiment_matrix_manifest.json").exists()


def test_command_templates_materialize_baseline_and_metric_plans(tmp_path) -> None:
    """命令模板应物化为显式 argv, 供后续 runner 审计和执行。"""
    baseline_plan = materialize_baseline_command_plan(
        "configs/baseline_command_templates.json",
        {
            "baseline_root": str(tmp_path / "baselines"),
            "events_path": str(tmp_path / "events.json"),
            "output_root": str(tmp_path / "baseline_outputs"),
        },
    )
    metric_plan = materialize_metric_command_plan(
        "configs/external_metric_command_templates.json",
        {
            "metric_root": str(tmp_path / "metrics"),
            "image_pairs_path": str(tmp_path / "pairs.json"),
            "reference_image_root": str(tmp_path / "ref"),
            "generated_image_root": str(tmp_path / "gen"),
            "image_prompt_rows_path": str(tmp_path / "prompts.json"),
            "output_root": str(tmp_path / "metric_outputs"),
        },
    )

    assert {spec.baseline_id for spec in baseline_plan} >= {"tree_ring", "gaussian_shading"}
    assert all(isinstance(spec.command, tuple) for spec in baseline_plan)
    assert {row["metric_name"] for row in metric_plan} == {"lpips", "fid", "clip_score"}
    assert all(isinstance(row["command"], list) for row in metric_plan)


def test_metric_plan_cli_collects_metric_rows(tmp_path) -> None:
    """metric plan CLI 应执行外部命令并汇总 metric_rows.json。"""
    metric_output = tmp_path / "lpips_rows.json"
    code = (
        "import json, pathlib; "
        f"pathlib.Path(r'{metric_output}').write_text(json.dumps([{{'event_id':'e1','method_name':'ceg','lpips':0.12}}]), encoding='utf-8')"
    )
    plan_path = tmp_path / "metric_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "metric_name": "lpips",
                    "command": [sys.executable, "-c", code],
                    "output_path": str(metric_output),
                    "timeout_seconds": 30,
                }
            ]
        ),
        encoding="utf-8",
    )
    specs = load_metric_command_plan(plan_path)
    manifest = build_metric_plan_manifest(specs)
    assert manifest["metric_command_count"] == 1

    output_root = tmp_path / "metric_outputs"
    subprocess.run(
        [sys.executable, "scripts/run_metric_plan.py", "--plan", str(plan_path), "--out", str(output_root)],
        cwd=".",
        check=True,
    )
    rows = json.loads((output_root / "metric_rows.json").read_text(encoding="utf-8"))
    assert rows[0]["lpips"] == 0.12
    assert (output_root / "metric_command_plan_manifest.json").exists()


def test_pdf_figure_export_writes_valid_pdf_preview(tmp_path) -> None:
    """PDF 图表导出器应从 figure specs 写出可识别的 PDF 文件。"""
    specs = {
        "figures": [
            {
                "figure_id": "main_detection_comparison",
                "title": "Main detection comparison",
                "chart_type": "bar",
                "takeaway": "CEG keeps high TPR with low clean FPR.",
                "encodings": {"x": "method_name", "y": "tpr"},
                "data": [
                    {"method_name": "ceg", "tpr": 0.95},
                    {"method_name": "tree_ring", "tpr": 0.72},
                ],
            }
        ]
    }
    manifest = render_figure_specs_pdf_package(specs, tmp_path)

    pdf_path = tmp_path / "paper_figures_preview.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert manifest["figure_count"] == 1
    assert (tmp_path / "paper_figures_pdf_manifest.json").exists()
