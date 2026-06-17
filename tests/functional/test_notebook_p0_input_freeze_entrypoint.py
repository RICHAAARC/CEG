"""验证 Notebook P0 输入冻结调度入口。"""

from __future__ import annotations

import csv
import json

import pytest

from experiments.pilot_input_value_pack_sheet import export_pilot_input_value_pack_fill_sheet
from paper_workflow.notebook_utils.protocol_entrypoint import (
    prepare_p0_input_materials_from_notebook,
    run_p0_input_freeze_from_notebook,
    validate_p0_fill_sheet_from_notebook,
)
from tests.functional.test_pilot_input_value_pack import REAL_VALUES
from tests.functional.test_pilot_input_value_pack_sheet import _prepare_value_pack


def _read_csv_rows(path):
    """读取 CSV 行, 供测试构造已填写的 value_json。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv_rows(path, rows, fieldnames) -> None:
    """写回 CSV 行, 保持导出表头不变。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fill_sheet_with_real_values(fill_sheet) -> None:
    """把测试用真实值写入 CSV, 用于验证 dry-run 不改写真正 value pack。"""
    rows = _read_csv_rows(fill_sheet)
    fieldnames = list(rows[0].keys())
    for row in rows:
        row["value_json"] = json.dumps(REAL_VALUES[row["task_id"]], ensure_ascii=False)
    _write_csv_rows(fill_sheet, rows, fieldnames)


@pytest.mark.quick
def test_notebook_p0_input_materials_exports_sheet_guidance_and_status(tmp_path) -> None:
    """Notebook 入口应能导出 P0 填写材料, 且不向 value pack 写入真实值。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)

    report = prepare_p0_input_materials_from_notebook(tmp_path)

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "fill_value_json_and_run_p0_dry_run"
    assert report["summary"]["fill_sheet_row_count"] == 19
    assert report["summary"]["guidance_row_count"] == 19
    assert report["summary"]["value_pack_blocking_item_count"] == 19
    assert (tmp_path / "pilot_input_value_pack_fill_sheet.csv").is_file()
    assert (tmp_path / "pilot_input_value_pack_fill_sheet_guidance.md").is_file()
    assert (tmp_path / "pilot_input_value_pack_fill_sheet_guidance.json").is_file()
    assert (tmp_path / "pilot_input_value_pack_status_report.json").is_file()
    assert (tmp_path / "pilot_input_value_pack_status_report.md").is_file()
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_notebook_p0_input_materials_preserves_existing_fill_sheet_by_default(tmp_path) -> None:
    """Notebook 准备入口默认不应覆盖用户已经填写过的 CSV。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    _fill_sheet_with_real_values(fill_sheet)

    report = prepare_p0_input_materials_from_notebook(tmp_path)

    rows = _read_csv_rows(fill_sheet)
    assert report["fill_sheet_report"]["skipped_export"] is True
    assert all(row["value_json"] for row in rows)


@pytest.mark.quick
def test_notebook_p0_fill_sheet_validation_blocks_empty_sheet_without_rewrite(tmp_path) -> None:
    """P0 CSV 预检应发现空 value_json, 且不回写 value pack。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)

    report = validate_p0_fill_sheet_from_notebook(tmp_path)

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
    assert report["write_on_pass"] is False
    assert report["write_performed"] is False
    assert report["summary"]["blocking_item_count"] == 19
    assert (tmp_path / "pilot_input_value_pack_fill_sheet_validation_report.json").is_file()
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_notebook_p0_fill_sheet_validation_can_pass_without_rewrite(tmp_path) -> None:
    """P0 CSV 预检通过时也不应回写 value pack, 应只建议进入 dry-run。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    _fill_sheet_with_real_values(fill_sheet)

    report = validate_p0_fill_sheet_from_notebook(tmp_path, require_pass=True)

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "run_p0_input_freeze_dry_run"
    assert report["write_on_pass"] is False
    assert report["write_performed"] is False
    assert report["summary"]["updated_entry_count"] == 19
    assert all("value" not in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_notebook_p0_input_freeze_defaults_to_dry_run_without_rewriting_value_pack(tmp_path) -> None:
    """Notebook 入口默认 dry-run, 应在隔离工作区校验且不改写真正 value pack。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    _fill_sheet_with_real_values(fill_sheet)

    report = run_p0_input_freeze_from_notebook(tmp_path)

    real_payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    dry_value_pack = tmp_path / "pilot_p0_input_freeze_dry_run_workspace" / value_pack_path.name
    assert report["overall_decision"] == "pass"
    assert report["dry_run"] is True
    assert (tmp_path / "pilot_p0_input_freeze_dry_run_report.json").is_file()
    assert (tmp_path / "pilot_p0_input_freeze_dry_run_report.md").is_file()
    assert all("value" not in entry for entry in real_payload["value_entries"])
    assert dry_value_pack.is_file()


@pytest.mark.quick
def test_notebook_p0_input_freeze_can_require_pass(tmp_path) -> None:
    """require_pass 为真时, Notebook 入口应把未通过的 P0 门禁显式抛出。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)

    with pytest.raises(RuntimeError, match="p0_csv_import"):
        run_p0_input_freeze_from_notebook(tmp_path, require_pass=True)


@pytest.mark.quick
def test_notebook_p0_input_freeze_can_run_formal_gate_after_dry_run(tmp_path) -> None:
    """显式关闭 dry-run 时, Notebook 入口应调度正式 P0 门禁并写出正式报告。"""
    value_pack_path, _ = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    _fill_sheet_with_real_values(fill_sheet)

    report = run_p0_input_freeze_from_notebook(tmp_path, dry_run=False, require_pass=True)

    real_payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["dry_run"] is False
    assert (tmp_path / "pilot_p0_input_freeze_report.json").is_file()
    assert (tmp_path / "pilot_p0_input_freeze_report.md").is_file()
    assert all("value" in entry for entry in real_payload["value_entries"])
