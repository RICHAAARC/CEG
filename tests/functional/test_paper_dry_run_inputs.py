"""验证论文 readiness dry-run 输入和端到端运行脚本。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.paper_fixture_factory import build_paper_dry_run_inputs, write_paper_dry_run_inputs


@pytest.mark.quick
def test_paper_dry_run_inputs_cover_methods_roles_and_baselines(tmp_path) -> None:
    """dry-run 输入应覆盖正负样本、全部 baseline 和 CEG 消融声明。"""
    bundle = build_paper_dry_run_inputs()
    manifest = write_paper_dry_run_inputs(tmp_path)

    sample_roles = {row["sample_role"] for row in bundle["events"]}
    baseline_ids = {row["baseline_id"] for row in bundle["baseline_observations"]}
    assert {"positive_source", "clean_negative", "attacked_negative"} <= sample_roles
    assert {"tree_ring", "gaussian_shading", "shallow_diffuse", "stable_signature_dee"} <= baseline_ids
    assert manifest["event_count"] == len(bundle["events"])
    assert (tmp_path / "events.json").exists()
    assert (tmp_path / "paper_dry_run_inputs_manifest.json").exists()


@pytest.mark.quick
def test_paper_readiness_dry_run_cli_builds_complete_outputs(tmp_path) -> None:
    """端到端 dry-run CLI 应生成完整论文输出包并通过 readiness。"""
    output_root = tmp_path / "dry_run"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_paper_readiness_dry_run.py",
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )

    dry_run_summary = json.loads((output_root / "paper_readiness_dry_run_summary.json").read_text(encoding="utf-8"))
    paper_summary = json.loads((output_root / "paper_outputs" / "paper_outputs_summary.json").read_text(encoding="utf-8"))
    readiness_report = json.loads((output_root / "paper_outputs" / "paper_readiness_report.json").read_text(encoding="utf-8"))
    assert dry_run_summary["return_code"] == 0
    assert paper_summary["paper_readiness_decision"] == "pass"
    assert readiness_report["overall_decision"] == "pass"
    assert (output_root / "paper_outputs" / "artifacts" / "standard_watermark_metrics.json").exists()
    assert (output_root / "paper_outputs" / "rendered_figures" / "paper_figures_report.html").exists()
    assert (output_root / "paper_outputs" / "pdf_figures" / "paper_figures_preview.pdf").read_bytes().startswith(b"%PDF")
