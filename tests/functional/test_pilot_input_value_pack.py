"""验证真实 pilot 输入值包模板与应用器。"""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import (
    build_pilot_input_plan_preflight_report,
    write_pilot_input_plan_preflight_report,
)
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import write_pilot_input_replacement_checklist
from experiments.pilot_input_value_pack import (
    apply_pilot_input_value_pack,
    build_pilot_input_value_pack_template,
)


REAL_VALUES = {
    "replace_prompt_text_placeholder": "a ceramic teapot on a wooden table",
    "replace_prompt_family_placeholder": "object_scene",
    "replace_license_note_placeholder": "local_test_prompt",
    "replace_split_placeholder": "calibration",
    "replace_sample_role_placeholder": "clean_negative",
    "replace_seed_placeholder": 1234,
    "replace_seed_role_placeholder": "primary",
    "replace_backend_type_placeholder": "external_command",
    "replace_model_id_placeholder": "local_sd_backend",
    "replace_scheduler_placeholder": "ddim",
    "replace_num_inference_steps_placeholder": 20,
    "replace_guidance_scale_placeholder": 7.5,
    "replace_image_size_placeholder": [512, 512],
    "replace_requires_huggingface_token_placeholder": False,
    "replace_watermark_method_placeholder": "ceg",
    "replace_payload_bits_placeholder": "10101010",
    "replace_watermark_strength_placeholder": 0.8,
    "replace_backend_command_placeholder": "python run_local_watermark.py",
    "replace_evidence_path_placeholder": "logs/watermark_run.json",
}


def _prepare_workspace_with_checklist(tmp_path):
    """生成带 preflight 和 replacement checklist 的测试工作区。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="value_pack")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    checklist = tmp_path / "pilot_input_plan_replacement_checklist.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)
    write_pilot_input_replacement_checklist(
        preflight_report_path=preflight,
        output_json_path=checklist,
    )
    return checklist


@pytest.mark.quick
def test_value_pack_template_scaffolds_one_entry_per_replacement_task(tmp_path) -> None:
    """值包模板应为每个替换任务生成一个待填写条目。"""
    checklist = _prepare_workspace_with_checklist(tmp_path)

    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)

    assert value_pack["manifest_status"] == "draft_requires_real_values"
    assert value_pack["summary"]["value_entry_count"] == 19
    assert all("value_placeholder" in item for item in value_pack["value_entries"])


@pytest.mark.quick
def test_apply_value_pack_requires_real_values(tmp_path) -> None:
    """没有真实 value 字段时, 应用器不能修改工作区计划。"""
    checklist = _prepare_workspace_with_checklist(tmp_path)
    value_pack_path = tmp_path / "pilot_input_value_pack.draft.json"
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    value_pack_path.write_text(json.dumps(value_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = apply_pilot_input_value_pack(workspace_root=tmp_path, value_pack_path=value_pack_path)

    assert report["overall_decision"] == "fail"
    assert report["summary"]["blocking_item_count"] == 19
    preflight_after = build_pilot_input_plan_preflight_report(workspace_root=tmp_path)
    assert preflight_after["overall_decision"] == "fail"


@pytest.mark.quick
def test_apply_value_pack_can_make_plan_preflight_pass(tmp_path) -> None:
    """填入真实 value 后, 应用器应替换计划文件中的占位字段。"""
    checklist = _prepare_workspace_with_checklist(tmp_path)
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    filled_pack = copy.deepcopy(value_pack)
    for entry in filled_pack["value_entries"]:
        entry["value"] = REAL_VALUES[entry["task_id"]]
    value_pack_path = tmp_path / "pilot_input_value_pack.filled.json"
    value_pack_path.write_text(json.dumps(filled_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = apply_pilot_input_value_pack(workspace_root=tmp_path, value_pack_path=value_pack_path)
    preflight_after = build_pilot_input_plan_preflight_report(workspace_root=tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["summary"]["applied_task_count"] == 19
    assert preflight_after["overall_decision"] == "pass"


@pytest.mark.quick
def test_value_pack_cli_scaffold_and_apply(tmp_path) -> None:
    """CLI 应能生成值包草稿, 并在未填写时作为硬门禁失败。"""
    checklist = _prepare_workspace_with_checklist(tmp_path)
    value_pack_path = tmp_path / "pilot_input_value_pack.draft.json"
    report_path = tmp_path / "pilot_input_value_pack_application_report.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/scaffold_pilot_input_value_pack.py",
            "--replacement-checklist",
            str(checklist),
            "--out",
            str(value_pack_path),
        ],
        cwd=".",
        check=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/apply_pilot_input_value_pack.py",
            "--workspace",
            str(tmp_path),
            "--value-pack",
            str(value_pack_path),
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_decision"] == "fail"
