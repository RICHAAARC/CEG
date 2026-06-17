"""验证真实图像生成 pilot 启动计划。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_image_generation_launch_plan import (
    build_pilot_image_generation_launch_plan,
    write_launch_variables_template,
)


def _write_json(path, payload) -> None:
    """写入 JSON 测试文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.quick
def test_launch_plan_fails_when_execution_readiness_fails(tmp_path) -> None:
    """execution readiness 未通过时, 不得生成可执行图像生成命令。"""
    readiness = tmp_path / "pilot_execution_readiness_report.json"
    launch_variables = tmp_path / "pilot_image_generation_launch_variables.draft.json"
    write_launch_variables_template(workspace_root=tmp_path, output_path=launch_variables)
    _write_json(readiness, {"overall_decision": "fail"})

    report = build_pilot_image_generation_launch_plan(
        workspace_root=tmp_path,
        readiness_report_path=readiness,
        launch_variables_path=launch_variables,
        template_path="configs/external_image_generation_command_templates.json",
    )

    assert report["overall_decision"] == "fail"
    assert report["summary"]["command_count"] == 0
    assert any(item["reason"] == "execution_readiness_not_pass" for item in report["blocking_items"])


@pytest.mark.quick
def test_launch_plan_materializes_command_when_ready(tmp_path) -> None:
    """readiness 和启动变量都通过后, 应物化 run_image_generation_plan 可消费的命令计划。"""
    readiness = tmp_path / "pilot_execution_readiness_report.json"
    launch_variables = tmp_path / "pilot_image_generation_launch_variables.json"
    _write_json(readiness, {"overall_decision": "pass"})
    _write_json(
        launch_variables,
        {
            "image_generation_root": "D:/external/sd_backend",
            "prompt_plan_path": "D:/pilot/prompt_plan.json",
            "output_root": str(tmp_path / "generated_images"),
            "model_config_path": "D:/pilot/model_config.json",
            "external_backend_command_json_path": "D:/pilot/p2_external_backend_command.json",
        },
    )

    report = build_pilot_image_generation_launch_plan(
        workspace_root=tmp_path,
        readiness_report_path=readiness,
        launch_variables_path=launch_variables,
        template_path="configs/external_image_generation_command_templates.json",
    )

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "run_image_generation_command_plan"
    assert report["summary"]["command_count"] == 1
    assert report["command_plan"][0]["backend_id"] == "external_sd_watermark_backend"


@pytest.mark.quick
def test_launch_plan_cli_writes_blocked_report(tmp_path) -> None:
    """CLI 应在未就绪时写出 blocked 报告, 且 --require-pass 返回非 0。"""
    readiness = tmp_path / "pilot_execution_readiness_report.json"
    launch_variables = tmp_path / "pilot_image_generation_launch_variables.draft.json"
    report_path = tmp_path / "pilot_image_generation_launch_plan_report.json"
    write_launch_variables_template(workspace_root=tmp_path, output_path=launch_variables)
    _write_json(readiness, {"overall_decision": "fail"})

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_image_generation_launch_plan.py",
            "--workspace",
            str(tmp_path),
            "--readiness-report",
            str(readiness),
            "--launch-variables",
            str(launch_variables),
            "--out-report",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_decision"] == "fail"
