"""验证 P0 输入用户交接包生成。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_preflight import write_pilot_input_plan_preflight_report
from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates
from experiments.pilot_input_replacement_checklist import write_pilot_input_replacement_checklist
from experiments.pilot_input_value_pack import build_pilot_input_value_pack_template
from experiments.pilot_input_value_pack_sheet import export_pilot_input_value_pack_fill_sheet
from experiments.pilot_user_handoff_bundle import (
    P0_HANDOFF_ACCEPTANCE_REPORT_NAME,
    P0_HANDOFF_APPLY_REPORT_NAME,
    P0_HANDOFF_MANIFEST_NAME,
    P0_HANDOFF_README_NAME,
    apply_pilot_p0_input_handoff_bundle,
    build_pilot_p0_input_handoff_bundle,
    validate_pilot_p0_input_handoff_bundle,
)
from tests.functional.test_pilot_input_value_pack import REAL_VALUES


def _prepare_value_pack(tmp_path):
    """生成测试用 value pack 草稿。"""
    scaffold_pilot_input_plan_templates(workspace_root=tmp_path, run_id="p0_handoff")
    preflight = tmp_path / "pilot_input_plan_preflight_report.json"
    checklist = tmp_path / "pilot_input_plan_replacement_checklist.json"
    value_pack_path = tmp_path / "pilot_input_value_pack.draft.json"
    write_pilot_input_plan_preflight_report(workspace_root=tmp_path, output_path=preflight)
    write_pilot_input_replacement_checklist(preflight_report_path=preflight, output_json_path=checklist)
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=checklist)
    value_pack_path.write_text(json.dumps(value_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return value_pack_path


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
def test_p0_input_handoff_bundle_preserves_existing_fill_sheet(tmp_path) -> None:
    """交接包生成默认不得覆盖用户已经填写过的 CSV。"""
    value_pack_path = _prepare_value_pack(tmp_path)
    fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack_path, output_csv_path=fill_sheet)
    rows = _read_csv_rows(fill_sheet)
    fieldnames = list(rows[0].keys())
    rows[0]["value_json"] = json.dumps(REAL_VALUES[rows[0]["task_id"]], ensure_ascii=False)
    _write_csv_rows(fill_sheet, rows, fieldnames)

    manifest = build_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)

    preserved_rows = _read_csv_rows(fill_sheet)
    handoff_root = tmp_path / "user_handoff" / "p0_input_handoff"
    handoff_manifest = json.loads((handoff_root / P0_HANDOFF_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert preserved_rows[0]["value_json"] == rows[0]["value_json"]
    assert manifest["overall_decision"] == "fail"
    assert manifest["validation_summary"]["blocking_item_count"] == 18
    assert handoff_manifest["fill_sheet_path"] == str(fill_sheet)
    assert (handoff_root / P0_HANDOFF_README_NAME).is_file()
    assert (handoff_root / "pilot_input_value_pack_fill_sheet.csv").is_file()
    assert "P0 输入冻结用户交接包" in (handoff_root / P0_HANDOFF_README_NAME).read_text(encoding="utf-8")


@pytest.mark.quick
def test_p0_input_handoff_bundle_cli_blocks_when_require_pass(tmp_path) -> None:
    """交接包 CLI 在仍有阻断项且要求通过时应返回非零码。"""
    _prepare_value_pack(tmp_path)
    out_dir = tmp_path / "handoff_out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_p0_input_handoff_bundle.py",
            "--workspace",
            str(tmp_path),
            "--out",
            str(out_dir),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((out_dir / P0_HANDOFF_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert manifest["overall_decision"] == "fail"
    assert manifest["validation_summary"]["blocking_item_count"] == 19
    assert (out_dir / P0_HANDOFF_README_NAME).is_file()


@pytest.mark.quick
def test_apply_p0_input_handoff_bundle_does_not_sync_on_validation_fail(tmp_path) -> None:
    """交接包填写表仍有阻断项时, 应用入口不得覆盖 canonical CSV 或导入 value pack。"""
    value_pack_path = _prepare_value_pack(tmp_path)
    build_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)
    canonical_fill_sheet = tmp_path / "pilot_input_value_pack_fill_sheet.csv"
    handoff_root = tmp_path / "user_handoff" / "p0_input_handoff"
    before = canonical_fill_sheet.read_text(encoding="utf-8-sig")

    report = apply_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
    assert report["canonical_fill_sheet_updated"] is False
    assert report["value_pack_import_performed"] is False
    assert canonical_fill_sheet.read_text(encoding="utf-8-sig") == before
    assert all("value" not in entry for entry in payload["value_entries"])
    assert (handoff_root / P0_HANDOFF_APPLY_REPORT_NAME).is_file()


@pytest.mark.quick
def test_apply_p0_input_handoff_bundle_syncs_and_imports_on_pass(tmp_path) -> None:
    """交接包填写表通过预检后, 应用入口应同步 canonical CSV 并导入 value pack。"""
    value_pack_path = _prepare_value_pack(tmp_path)
    build_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)
    handoff_root = tmp_path / "user_handoff" / "p0_input_handoff"
    handoff_fill_sheet = handoff_root / "pilot_input_value_pack_fill_sheet.csv"
    rows = _read_csv_rows(handoff_fill_sheet)
    fieldnames = list(rows[0].keys())
    for row in rows:
        row["value_json"] = json.dumps(REAL_VALUES[row["task_id"]], ensure_ascii=False)
    _write_csv_rows(handoff_fill_sheet, rows, fieldnames)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/apply_pilot_p0_input_handoff_bundle.py",
            "--workspace",
            str(tmp_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    payload = json.loads(value_pack_path.read_text(encoding="utf-8"))
    report = json.loads((handoff_root / P0_HANDOFF_APPLY_REPORT_NAME).read_text(encoding="utf-8"))
    canonical_rows = _read_csv_rows(tmp_path / "pilot_input_value_pack_fill_sheet.csv")
    assert completed.returncode == 0
    assert report["overall_decision"] == "pass"
    assert report["canonical_fill_sheet_updated"] is True
    assert report["value_pack_import_performed"] is True
    assert canonical_rows[0]["value_json"] == rows[0]["value_json"]
    assert all("value" in entry for entry in payload["value_entries"])


@pytest.mark.quick
def test_validate_p0_input_handoff_bundle_passes_when_ready_for_user(tmp_path) -> None:
    """交接包文件完整时, 即使 CSV 仍待填写, handoff 验收也应通过。"""
    _prepare_value_pack(tmp_path)
    build_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)
    apply_pilot_p0_input_handoff_bundle(workspace_root=tmp_path, write_on_pass=False)

    report = validate_pilot_p0_input_handoff_bundle(workspace_root=tmp_path, require_apply_report=True)

    handoff_root = tmp_path / "user_handoff" / "p0_input_handoff"
    assert report["overall_decision"] == "pass"
    assert report["validation_summary"]["overall_decision"] == "fail"
    assert report["validation_summary"]["blocking_item_count"] == 19
    assert report["apply_summary"]["canonical_fill_sheet_updated"] is False
    assert (handoff_root / P0_HANDOFF_ACCEPTANCE_REPORT_NAME).is_file()


@pytest.mark.quick
def test_validate_p0_input_handoff_bundle_cli_blocks_missing_file(tmp_path) -> None:
    """缺少必要 handoff 文件时, 验收 CLI 应失败。"""
    _prepare_value_pack(tmp_path)
    build_pilot_p0_input_handoff_bundle(workspace_root=tmp_path)
    handoff_root = tmp_path / "user_handoff" / "p0_input_handoff"
    (handoff_root / "pilot_input_value_pack_fill_sheet.csv").unlink()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_p0_input_handoff_bundle.py",
            "--workspace",
            str(tmp_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    report = json.loads((handoff_root / P0_HANDOFF_ACCEPTANCE_REPORT_NAME).read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert report["overall_decision"] == "fail"
    assert report["blocking_items"][0]["reason"] == "missing_required_handoff_file"
