"""验证 P2 图像生成 GPU 交接清单。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_p2_gpu_handoff import (
    P2_GPU_HANDOFF_CHECKLIST_NAME,
    P2_GPU_HANDOFF_RUNBOOK_NAME,
    write_p2_image_generation_gpu_handoff,
)


def _write_json(path, payload) -> None:
    """写出测试用 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_ready_workspace(tmp_path) -> None:
    """准备 P0 / P1 均通过的最小工作区。"""
    _write_json(
        tmp_path / "pilot_p0_input_freeze_report.json",
        {"overall_decision": "pass", "recommended_next_stage": "image_generation_launch_plan", "summary": {}},
    )
    _write_json(
        tmp_path / "pilot_image_generation_launch_plan_report.json",
        {"overall_decision": "pass", "recommended_next_stage": "run_image_generation_command_plan", "summary": {"command_count": 1}},
    )
    _write_json(
        tmp_path / "image_generation_command_plan.json",
        [
            {
                "backend_id": "external_sd_watermark_backend",
                "command": [
                    "python",
                    "D:/Code/CEG/scripts/run_image_generation_plan.py",
                    "--prompt-plan",
                    "D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/prompts/prompt_plan.draft.json",
                    "--out",
                    "D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images",
                ],
                "output_root": "D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images",
                "working_directory": "D:/Code/CEG",
                "timeout_seconds": 7200,
            }
        ],
    )


@pytest.mark.quick
def test_p2_gpu_handoff_checklist_requires_prompt_plan_output(tmp_path) -> None:
    """P2 交接清单必须包含接收门禁要求的 prompt_plan.json。"""
    _prepare_ready_workspace(tmp_path)

    checklist = write_p2_image_generation_gpu_handoff(workspace_root=tmp_path)

    handoff_root = tmp_path / "gpu_handoff" / "p2_image_generation"
    required = {row["relative_path"] for row in checklist["required_outputs"]}
    assert checklist["overall_decision"] == "ready_for_user_colab_gpu_execution"
    assert "prompt_plan.json" in required
    assert "image_pairs.json" in required
    assert "image_manifests/image_generation_manifest.json" in required
    assert "image_manifests/image_pair_manifest.json" in required
    assert checklist["secret_handling"]["requires_huggingface_token"] is True
    assert checklist["colab_command_plan"][0]["working_directory"] == "/content/CEG"
    assert checklist["colab_command_plan"][0]["output_root"].startswith(
        "/content/drive/MyDrive/CEG/pilot_runs/"
    )
    assert checklist["colab_shell_commands"]
    assert "D:/" not in checklist["colab_shell_commands"][0]
    assert "D:\\" not in checklist["colab_shell_commands"][0]
    assert checklist["entrypoint_checks"][0]["status"] == "repo_entrypoint_exists"
    assert checklist["execution_warnings"] == []
    assert checklist["colab_acceptance_commands"][0].startswith(
        "python scripts/validate_pilot_image_generation_outputs.py --output-root /content/drive/"
    )
    assert "D:/" in checklist["local_acceptance_commands"][0]
    assert (handoff_root / P2_GPU_HANDOFF_CHECKLIST_NAME).is_file()
    assert (handoff_root / P2_GPU_HANDOFF_RUNBOOK_NAME).is_file()
    assert "不能用 mock 图像替代真实 P2 图像" in (handoff_root / P2_GPU_HANDOFF_RUNBOOK_NAME).read_text(encoding="utf-8")


@pytest.mark.quick
def test_p2_gpu_handoff_warns_when_template_entrypoint_is_missing(tmp_path) -> None:
    """命令计划指向不存在的仓库入口时, handoff 应明确提示需要外部 backend。"""
    _prepare_ready_workspace(tmp_path)
    _write_json(
        tmp_path / "image_generation_command_plan.json",
        [
            {
                "backend_id": "external_sd_watermark_backend",
                "command": ["python", "D:/Code/CEG/run_image_generation.py"],
                "output_root": "D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images",
                "working_directory": "D:/Code/CEG",
                "timeout_seconds": 7200,
            }
        ],
    )

    checklist = write_p2_image_generation_gpu_handoff(workspace_root=tmp_path)

    assert checklist["overall_decision"] == "ready_for_user_colab_gpu_execution"
    assert checklist["entrypoint_checks"][0]["status"] == "repo_entrypoint_missing"
    assert checklist["execution_warnings"][0]["warning_type"] == "repo_entrypoint_missing"
    assert "需要用户提供外部 backend 脚本" in checklist["execution_warnings"][0]["message"]


@pytest.mark.quick
def test_p2_gpu_handoff_cli_blocks_when_p1_missing(tmp_path) -> None:
    """P1 报告缺失时, CLI 在 require-ready 下应失败。"""
    _write_json(
        tmp_path / "pilot_p0_input_freeze_report.json",
        {"overall_decision": "pass", "recommended_next_stage": "image_generation_launch_plan", "summary": {}},
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_p2_gpu_handoff.py",
            "--workspace",
            str(tmp_path),
            "--require-ready",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    checklist = json.loads(
        (tmp_path / "gpu_handoff" / "p2_image_generation" / P2_GPU_HANDOFF_CHECKLIST_NAME).read_text(encoding="utf-8")
    )
    assert completed.returncode == 1
    assert checklist["overall_decision"] == "fail"
    assert any(item["gate"] == "p1_image_generation_launch_plan" for item in checklist["blocking_items"])
