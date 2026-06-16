"""验证真实 pilot 输入计划预检门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import build_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates


def _write_json(path, payload) -> None:
    """写入测试 JSON 文件, 便于构造无占位字段的最小真实配置。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_minimal_real_plan_files(workspace) -> None:
    """写入不含占位字段的最小真实 pilot 输入计划。"""
    _write_json(
        workspace / "inputs" / "prompts" / "prompt_plan.draft.json",
        {
            "artifact_name": "prompt_plan.json",
            "manifest_status": "pilot_ready",
            "run_id": "real_plan",
            "prompts": [
                {
                    "prompt_id": "prompt_0001",
                    "prompt_text": "a ceramic teapot on a wooden table",
                    "prompt_family": "object_scene",
                    "license_note": "local_test_prompt",
                }
            ],
        },
    )
    _write_json(
        workspace / "inputs" / "prompts" / "split_plan.draft.json",
        {
            "artifact_name": "split_plan.json",
            "manifest_status": "pilot_ready",
            "run_id": "real_plan",
            "split_policy": "calibration_clean_negative_for_threshold_test_split_for_evaluation",
            "assignments": [
                {"prompt_id": "prompt_0001", "split": "calibration", "sample_role": "clean_negative"}
            ],
        },
    )
    _write_json(
        workspace / "inputs" / "prompts" / "seed_plan.draft.json",
        {
            "artifact_name": "seed_plan.json",
            "manifest_status": "pilot_ready",
            "run_id": "real_plan",
            "seeds": [{"prompt_id": "prompt_0001", "seed": 1234, "seed_role": "primary"}],
        },
    )
    _write_json(
        workspace / "configs" / "model_config.draft.json",
        {
            "artifact_name": "model_config.json",
            "manifest_status": "pilot_ready",
            "run_id": "real_plan",
            "backend_type": "external_command",
            "model_id": "local_sd_backend",
            "scheduler": "ddim",
            "num_inference_steps": 20,
            "guidance_scale": 7.5,
            "image_size": [512, 512],
            "requires_huggingface_token": False,
        },
    )
    _write_json(
        workspace / "configs" / "watermark_config.draft.json",
        {
            "artifact_name": "watermark_config.json",
            "manifest_status": "pilot_ready",
            "run_id": "real_plan",
            "watermark_method": "ceg",
            "payload_bits": "10101010",
            "watermark_strength": 0.8,
            "backend_command": "python run_local_watermark.py",
            "evidence_path": "logs/watermark_run.json",
        },
    )


@pytest.mark.quick
def test_pilot_input_plan_preflight_fails_on_scaffolded_placeholders(tmp_path) -> None:
    """脚手架模板仍含占位字段, 预检必须阻止真实运行。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="placeholder_plan")

    report = build_pilot_input_plan_preflight_report(workspace_root=tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "replace_pilot_input_plan_placeholders"
    assert report["summary"]["placeholder_finding_count"] > 0
    assert report["summary"]["missing_file_count"] == 0


@pytest.mark.quick
def test_pilot_input_plan_preflight_passes_on_real_minimal_plans(tmp_path) -> None:
    """所有占位字段替换后, 预检允许进入真实图像生成 pilot。"""
    _write_minimal_real_plan_files(tmp_path)

    report = build_pilot_input_plan_preflight_report(workspace_root=tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "real_image_generation_pilot"
    assert report["summary"]["blocking_item_count"] == 0


@pytest.mark.quick
def test_pilot_input_plan_preflight_cli_writes_report_and_hard_gate(tmp_path) -> None:
    """CLI 应写出报告, 且 --require-pass 在占位字段存在时返回非 0。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="placeholder_cli_plan")
    report_path = tmp_path / "pilot_input_plan_preflight_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_input_plan_templates.py",
            "--workspace",
            str(tmp_path),
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
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
