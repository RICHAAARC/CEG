"""验证真实 pilot 输入 value pack CSV 填写表导出和导入。"""

from __future__ import annotations

import csv
import copy
import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import write_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import write_pilot_input_replacement_checklist
from experiments.pilot_input_value_pack import build_pilot_input_value_pack_template
from experiments.pilot_input_value_pack_sheet import (
    export_pilot_input_value_pack_fill_sheet,
    export_pilot_input_value_pack_fill_sheet_guidance,
    import_and_write_pilot_input_value_pack_fill_sheet,
)
from experiments.pilot_input_value_pack_status import build_pilot_input_value_pack_status
from tests.functional.test_pilot_input_value_pack import REAL_VALUES


def _prepare_value_pack(tmp_path):
    """生成测试用 value pack 草稿。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="value_pack_sheet")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    checklist = tmp_path / "pilot_input_plan_replacement_checklist.json"
    value_pack_path = tmp_path / "pilot_input_value_pack.draft.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)
    write_pilot_input_replacement_checklist(preflight_report_path=preflight, output_json_path=checklist)
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    value_pack_path.write_text(json.dumps(value_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return value_pack_path, value_pack


def _read_csv_rows(path):
    """读取 CSV 行。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv_rows(path, rows, fieldnames):
    """写回 CSV 行。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.quick
def test_export_value_pack_fill_sheet_writes_one_row_per_entry(tmp_path) -> None:
    """导出的 CSV 填写表应与 value pack 条目一一对应。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"

    report = export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)

    rows = _read_csv_rows(fill_sheet)
    assert report["overall_decision"] == "pass"
    assert report["row_count"] == 19
    assert len(rows) == 19
    assert {"task_id", "replacement_key", "value_json"}.issubset(rows[0])


@pytest.mark.quick
def test_export_value_pack_fill_sheet_guidance_does_not_rewrite_value_pack(tmp_path) -> None:
    """填写指南只应提供格式说明, 不应向 value pack 写入真实 value。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    guidance_md = tmp_path / "pilot_input_value_pack_fill_sheet_guidance.md"
    guidance_json = tmp_path / "pilot_input_value_pack_fill_sheet_guidance.json"

    report = export_pilot_input_value_pack_fill_sheet_guidance(
        value_pack_path=value_pack_path,
        output_markdown_path=guidance_md,
        output_json_path=guidance_json,
    )

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    guidance_payload = json.loads(guidance_json.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["guidance_only"] is True
    assert report["summary"]["guidance_row_count"] == 19
    assert len(guidance_payload["guidance_rows"]) == 19
    assert guidance_md.is_file()
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_import_value_pack_fill_sheet_blocks_empty_values(tmp_path) -> None:
    """CSV 仍有空 value_json 时, 导入器不应回写 value pack。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    report_path = tmp_path / "import_report.json"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)

    report = import_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack_path,
        input_csv_path=fill_sheet,
        output_value_pack_path=None,
        report_path=report_path,
    )

    assert report["overall_decision"] == "fail"
    assert report["summary"]["blocking_item_count"] == 19
    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_import_value_pack_fill_sheet_blocks_invalid_types_without_rewrite(tmp_path) -> None:
    """CSV 值可解析但类型错误时, 导入器不应回写 value pack。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    report_path = tmp_path / "import_report.json"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    rows = _read_csv_rows(fill_sheet)
    fieldnames = list(rows[0].keys())
    for row in rows:
        row["value_json"] = json.dumps(REAL_VALUES[row["task_id"]], ensure_ascii=False)
        if row["replacement_key"] == "requires_huggingface_token":
            row["value_json"] = json.dumps("false")
    _write_csv_rows(fill_sheet, rows, fieldnames)

    report = import_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack_path,
        input_csv_path=fill_sheet,
        output_value_pack_path=None,
        report_path=report_path,
    )

    assert report["overall_decision"] == "fail"
    assert report["summary"]["blocking_item_count"] == 1
    assert report["summary"]["updated_entry_count"] == 0
    assert report["updated_entries"] == []
    assert report["blocking_items"][0]["validation_errors"] == ["must_be_boolean"]
    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_import_filled_value_pack_sheet_can_pass_status_validation(tmp_path) -> None:
    """CSV 填写真实 JSON 值后, 导入结果应通过 value pack 状态校验。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    report_path = tmp_path / "import_report.json"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    rows = _read_csv_rows(fill_sheet)
    fieldnames = list(rows[0].keys())
    for row in rows:
        row["value_json"] = json.dumps(REAL_VALUES[row["task_id"]], ensure_ascii=False)
    _write_csv_rows(fill_sheet, rows, fieldnames)

    report = import_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack_path,
        input_csv_path=fill_sheet,
        output_value_pack_path=None,
        report_path=report_path,
    )
    status = build_pilot_input_value_pack_status(workspace_root=tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["summary"]["updated_entry_count"] == 19
    assert status["overall_decision"] == "pass"
    assert status["summary"]["blocking_item_count"] == 0


@pytest.mark.quick
def test_value_pack_fill_sheet_cli_roundtrip(tmp_path) -> None:
    """CLI 应支持导出填写表, 并在未填写时用 require-pass 阻断导入。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    report_path = tmp_path / "pilot_input_value_pack_fill_sheet_import_report.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/export_pilot_input_value_pack_fill_sheet.py",
            "--workspace",
            str(tmp_path),
            "--value-pack",
            str(value_pack_path),
            "--out",
            str(fill_sheet),
        ],
        cwd=".",
        check=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/import_pilot_input_value_pack_fill_sheet.py",
            "--workspace",
            str(tmp_path),
            "--value-pack",
            str(value_pack_path),
            "--fill-sheet",
            str(fill_sheet),
            "--out-report",
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
