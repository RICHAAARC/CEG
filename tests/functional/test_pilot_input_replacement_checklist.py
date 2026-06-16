"""验证真实 pilot 输入替换清单生成。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import write_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import build_pilot_input_replacement_checklist


@pytest.mark.quick
def test_replacement_checklist_turns_preflight_findings_into_tasks(tmp_path) -> None:
    """preflight 中的占位字段应转换为明确替换任务。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="replacement_tasks")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)

    checklist = build_pilot_input_replacement_checklist(preflight_report_path=preflight)

    assert checklist["overall_decision"] == "fail"
    assert checklist["recommended_next_stage"] == "rerun_pilot_input_plan_preflight"
    assert checklist["summary"]["replacement_task_count"] == 19
    task_ids = {task["task_id"] for task in checklist["replacement_tasks"]}
    assert "replace_prompt_text_placeholder" in task_ids
    assert "replace_model_id_placeholder" in task_ids
    assert "replace_watermark_method_placeholder" in task_ids


@pytest.mark.quick
def test_replacement_checklist_cli_writes_json_and_markdown(tmp_path) -> None:
    """CLI 应同时写出机器可读 JSON 和人工可读 Markdown。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="replacement_cli")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    out_json = tmp_path / "pilot_input_plan_replacement_checklist.json"
    out_md = tmp_path / "pilot_input_plan_replacement_checklist.md"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_input_replacement_checklist.py",
            "--preflight-report",
            str(preflight),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=".",
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["summary"]["replacement_task_count"] == 19
    assert "pilot 输入计划占位字段替换清单" in markdown
