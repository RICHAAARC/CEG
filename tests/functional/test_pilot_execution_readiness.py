"""验证真实 pilot 执行就绪聚合报告。"""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from experiments.pilot_execution_readiness import build_pilot_execution_readiness_report
from experiments.pilot_input_plan_preflight import write_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import write_pilot_input_replacement_checklist
from experiments.pilot_input_value_pack import (
    apply_and_write_pilot_input_value_pack,
    build_pilot_input_value_pack_template,
)
from tests.functional.test_pilot_input_value_pack import REAL_VALUES


def _prepare_not_ready_workspace(tmp_path):
    """准备一个仍未填写真实值包的工作区。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="execution_readiness")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    checklist = tmp_path / "pilot_input_plan_replacement_checklist.json"
    value_pack = tmp_path / "pilot_input_value_pack.draft.json"
    application = tmp_path / "pilot_input_value_pack_application_report.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)
    write_pilot_input_replacement_checklist(
        preflight_report_path=preflight,
        output_json_path=checklist,
    )
    value_pack_payload = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    value_pack.write_text(json.dumps(value_pack_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply_and_write_pilot_input_value_pack(
        workspace_root=tmp_path,
        value_pack_path=value_pack,
        report_path=application,
    )
    return preflight, checklist, value_pack, application


@pytest.mark.quick
def test_execution_readiness_fails_when_value_pack_is_not_filled(tmp_path) -> None:
    """值包未填写时, 聚合报告必须阻止真实图像生成。"""
    _prepare_not_ready_workspace(tmp_path)

    report = build_pilot_execution_readiness_report(workspace_root=tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "complete_value_pack_and_rerun_preflight"
    assert report["summary"]["blocking_gate_count"] == 2


@pytest.mark.quick
def test_execution_readiness_passes_after_value_pack_and_preflight_pass(tmp_path) -> None:
    """值包应用和 preflight 都通过后, 聚合报告允许进入真实图像生成 pilot。"""
    preflight, checklist, value_pack, application = _prepare_not_ready_workspace(tmp_path)
    value_pack_payload = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    filled_pack = copy.deepcopy(value_pack_payload)
    for entry in filled_pack["value_entries"]:
        entry["value"] = REAL_VALUES[entry["task_id"]]
    value_pack.write_text(json.dumps(filled_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply_and_write_pilot_input_value_pack(
        workspace_root=tmp_path,
        value_pack_path=value_pack,
        report_path=application,
    )
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)

    report = build_pilot_execution_readiness_report(workspace_root=tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "real_image_generation_pilot"
    assert report["summary"]["blocking_gate_count"] == 0


@pytest.mark.quick
def test_execution_readiness_cli_writes_report_and_hard_gate(tmp_path) -> None:
    """CLI 应写出报告, 且 --require-pass 在未就绪时返回非 0。"""
    _prepare_not_ready_workspace(tmp_path)
    out = tmp_path / "pilot_execution_readiness_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_execution_readiness_report.py",
            "--workspace",
            str(tmp_path),
            "--out",
            str(out),
            "--require-pass",
        ],
        cwd=".",
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_decision"] == "fail"
