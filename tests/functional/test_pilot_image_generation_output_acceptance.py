"""验证 pilot 图像生成输出接收门禁。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.image_generation_backend import write_mock_image_generation_from_prompt_plan
from experiments.pilot_image_generation_output_acceptance import (
    build_pilot_image_generation_output_acceptance_report,
)


@pytest.mark.quick
def test_image_generation_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空输出目录必须失败, 避免把未运行 backend 的目录推进到 attack。"""
    report = build_pilot_image_generation_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_image_generation_backend_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 4
    assert report["summary"]["blocking_issue_count"] >= 4


@pytest.mark.quick
def test_image_generation_output_acceptance_passes_mock_contract(tmp_path) -> None:
    """mock backend 产出的契约完整文件应能通过接收门禁。"""
    write_mock_image_generation_from_prompt_plan(
        [
            {
                "prompt_id": "prompt_001",
                "prompt_text": "contract validation prompt",
                "event_id": "event_001",
                "image_id": "image_001",
                "seed": 7,
                "split": "test",
                "sample_role": "positive",
            }
        ],
        tmp_path,
    )

    report = build_pilot_image_generation_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "image_attack_pilot"
    assert report["summary"]["image_pair_count"] == 1
    assert report["summary"]["blocking_issue_count"] == 0
    assert report["image_pair_checks"][0]["clean_image"]["exists"] is True
    assert report["image_pair_checks"][0]["watermarked_image"]["exists"] is True


@pytest.mark.quick
def test_image_generation_output_acceptance_fails_missing_watermarked_file(tmp_path) -> None:
    """image_pairs 指向不存在的 watermarked 图像时必须失败。"""
    write_mock_image_generation_from_prompt_plan(
        [
            {
                "prompt_id": "prompt_001",
                "prompt_text": "missing watermarked image prompt",
                "event_id": "event_001",
                "image_id": "image_001",
                "seed": 9,
            }
        ],
        tmp_path,
    )
    image_pairs = json.loads((tmp_path / "image_pairs.json").read_text(encoding="utf-8"))
    watermarked_path = Path(image_pairs[0]["watermarked_image_path"])
    watermarked_path.unlink()

    report = build_pilot_image_generation_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_watermarked_image_file" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_image_generation_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_image_generation_outputs.py",
            "--output-root",
            str(tmp_path / "missing_output_root"),
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
    assert report["artifact_name"] == "pilot_image_generation_output_acceptance_report.json"
