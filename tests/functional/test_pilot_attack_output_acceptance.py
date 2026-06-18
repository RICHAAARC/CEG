"""验证 pilot attack 输出接收门禁。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.image_generation_backend import write_mock_image_generation_from_prompt_plan
from experiments.pilot_attack_output_acceptance import build_pilot_attack_output_acceptance_report
from main.analysis.attack_images import run_attack_workflow


@pytest.mark.quick
def test_attack_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空 attack 输出目录必须失败, 避免未运行 attack 时进入 detection。"""
    report = build_pilot_attack_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_attack_backend_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 3
    assert report["summary"]["blocking_issue_count"] >= 3


@pytest.mark.quick
def test_attack_output_acceptance_passes_attack_workflow_contract(tmp_path) -> None:
    """run_attack_workflow 产出的完整契约应通过接收门禁。"""
    image_root = tmp_path / "images"
    attack_root = tmp_path / "attacks"
    write_mock_image_generation_from_prompt_plan(
        [
            {
                "prompt_id": "prompt_001",
                "prompt_text": "attack acceptance prompt",
                "event_id": "event_001",
                "image_id": "image_001",
                "seed": 11,
            }
        ],
        image_root,
    )
    rows = json.loads((image_root / "image_pairs.json").read_text(encoding="utf-8"))
    run_attack_workflow(rows, attack_root, attack_families=("brightness_contrast", "gaussian_noise"))

    report = build_pilot_attack_output_acceptance_report(attack_root)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "ceg_detection_pilot"
    assert report["summary"]["attacked_record_count"] == 4
    assert report["summary"]["attacked_pair_count"] == 4
    assert report["summary"]["blocking_issue_count"] == 0
    assert all(item["attacked_image_path"]["exists"] for item in report["attacked_record_checks"])


@pytest.mark.quick
def test_attack_output_acceptance_fails_when_attacked_file_missing(tmp_path) -> None:
    """manifest 指向的 attacked 图像缺失时必须失败。"""
    image_root = tmp_path / "images"
    attack_root = tmp_path / "attacks"
    write_mock_image_generation_from_prompt_plan(
        [
            {
                "prompt_id": "prompt_001",
                "prompt_text": "missing attacked file prompt",
                "event_id": "event_001",
                "image_id": "image_001",
                "seed": 13,
            }
        ],
        image_root,
    )
    rows = json.loads((image_root / "image_pairs.json").read_text(encoding="utf-8"))
    run_attack_workflow(rows, attack_root, attack_families=("brightness_contrast",))
    attacked_manifest = json.loads(
        (attack_root / "image_manifests" / "attacked_image_manifest.json").read_text(encoding="utf-8")
    )
    Path(attacked_manifest["attacked_images"][0]["attacked_image_path"]).unlink()

    report = build_pilot_attack_output_acceptance_report(attack_root)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_attacked_image_file" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_attack_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "attack_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_attack_outputs.py",
            "--output-root",
            str(tmp_path / "missing_attack_root"),
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
    assert report["artifact_name"] == "pilot_attack_output_acceptance_report.json"
