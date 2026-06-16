"""验证真实 pilot 输入 value pack 填写状态报告。"""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import write_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import write_pilot_input_replacement_checklist
from experiments.pilot_input_value_pack import build_pilot_input_value_pack_template
from experiments.pilot_input_value_pack_status import (
    build_pilot_input_value_pack_status,
    write_pilot_input_value_pack_status,
)
from tests.functional.test_pilot_input_value_pack import REAL_VALUES


def _prepare_value_pack(tmp_path):
    """生成测试用 value pack 草稿。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="value_pack_status")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    checklist = tmp_path / "pilot_input_plan_replacement_checklist.json"
    value_pack_path = tmp_path / "pilot_input_value_pack.draft.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)
    write_pilot_input_replacement_checklist(preflight_report_path=preflight, output_json_path=checklist)
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    value_pack_path.write_text(json.dumps(value_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return value_pack_path, value_pack


@pytest.mark.quick
def test_value_pack_status_reports_missing_values(tmp_path) -> None:
    """未填写 value 字段时, 状态报告应列出所有阻断条目。"""
    _prepare_value_pack(tmp_path)

    report = build_pilot_input_value_pack_status(workspace_root=tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "fill_missing_real_values_in_value_pack"
    assert report["summary"]["missing_count"] == 19
    assert report["summary"]["blocking_item_count"] == 19


@pytest.mark.quick
def test_value_pack_status_passes_when_all_values_are_filled(tmp_path) -> None:
    """所有 value 字段填写为真实值后, 状态报告应允许进入应用阶段。"""
    value_pack_path, value_pack = _prepare_value_pack(tmp_path)
    filled = copy.deepcopy(value_pack)
    for entry in filled["value_entries"]:
        entry["value"] = REAL_VALUES[entry["task_id"]]
    value_pack_path.write_text(json.dumps(filled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = build_pilot_input_value_pack_status(workspace_root=tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "apply_pilot_input_value_pack"
    assert report["summary"]["filled_count"] == 19
    assert report["summary"]["blocking_item_count"] == 0


@pytest.mark.quick
def test_value_pack_status_writes_json_and_markdown(tmp_path) -> None:
    """状态报告应同时写出 JSON 和 Markdown, 供机器与人工检查复用。"""
    _prepare_value_pack(tmp_path)
    out_json = tmp_path / "status.json"
    out_md = tmp_path / "status.md"

    report = write_pilot_input_value_pack_status(
        workspace_root=tmp_path,
        value_pack_path=None,
        output_json_path=out_json,
        output_markdown_path=out_md,
    )

    assert report["overall_decision"] == "fail"
    assert json.loads(out_json.read_text(encoding="utf-8"))["artifact_name"] == "pilot_input_value_pack_status_report.json"
    assert "pilot 输入 value pack 填写状态" in out_md.read_text(encoding="utf-8")


@pytest.mark.quick
def test_value_pack_status_cli_require_pass_fails_on_missing_values(tmp_path) -> None:
    """CLI 在 value 未填写时应写出报告, 并在 require-pass 下返回非零退出码。"""
    _prepare_value_pack(tmp_path)
    out_json = tmp_path / "status.json"
    out_md = tmp_path / "status.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_input_value_pack_status.py",
            "--workspace",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-markdown",
            str(out_md),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert out_json.is_file()
    assert out_md.is_file()
