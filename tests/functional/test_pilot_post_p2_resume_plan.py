"""验证 P2 后 P3 / P4 接续计划。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_post_p2_resume_plan import write_post_p2_resume_plan


def _write_json(path, payload) -> None:
    """写出测试 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.quick
def test_post_p2_resume_plan_blocks_until_p2_pass(tmp_path) -> None:
    """P2 未通过时, 接续计划只能作为预案, 不能声明可执行。"""
    _write_json(tmp_path / "pilot_image_generation_output_acceptance_report.json", {"overall_decision": "fail"})

    plan = write_post_p2_resume_plan(workspace_root=tmp_path)

    assert plan["overall_decision"] == "blocked_until_p2_pass"
    assert any(item["warning_type"] == "p2_not_passed_yet" for item in plan["execution_warnings"])
    assert any("run_image_attack_workflow.py" in row["shell_command"] for row in plan["command_rows"])
    assert (tmp_path / "gpu_handoff" / "post_p2_resume" / "pilot_post_p2_resume_plan.json").is_file()
    assert (tmp_path / "gpu_handoff" / "post_p2_resume" / "pilot_post_p2_resume_runbook.md").is_file()


@pytest.mark.quick
def test_post_p2_resume_plan_ready_when_p2_passes(tmp_path) -> None:
    """P2 通过后, 接续计划应给出 attack 和 detection 命令。"""
    _write_json(tmp_path / "pilot_image_generation_output_acceptance_report.json", {"overall_decision": "pass"})

    plan = write_post_p2_resume_plan(workspace_root=tmp_path)

    commands = [row["shell_command"] for row in plan["command_rows"]]
    assert plan["overall_decision"] == "ready_after_p2_pass"
    assert any("validate_pilot_attack_outputs.py" in command for command in commands)
    assert any("run_ceg_detection_producer.py" in command for command in commands)
    assert any("validate_pilot_detection_outputs.py" in command for command in commands)


@pytest.mark.quick
def test_post_p2_resume_plan_cli_require_ready_fails_before_p2_pass(tmp_path) -> None:
    """CLI 在 require-ready 下必须阻止 P2 失败状态。"""
    _write_json(tmp_path / "pilot_image_generation_output_acceptance_report.json", {"overall_decision": "fail"})

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_post_p2_resume_plan.py",
            "--workspace",
            str(tmp_path),
            "--require-ready",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    report = json.loads((tmp_path / "gpu_handoff" / "post_p2_resume" / "pilot_post_p2_resume_plan.json").read_text(encoding="utf-8"))
    assert report["overall_decision"] == "blocked_until_p2_pass"
