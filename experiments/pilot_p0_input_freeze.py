"""真实 pilot P0 输入冻结聚合门禁。

该模块把 P0 阶段的多个轻量门禁串联为一个可审计报告。它不生成真实实验值,
也不运行 SD、watermark、attack 或 detector。它只负责在用户填写 `value_json`
之后, 按顺序验证并应用真实 pilot 输入配置。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.pilot_execution_readiness import (
    EXECUTION_READINESS_REPORT_NAME,
    write_pilot_execution_readiness_report,
)
from experiments.pilot_input_plan_preflight import PREFLIGHT_REPORT_NAME, write_pilot_input_plan_preflight_report
from experiments.pilot_input_value_pack import (
    VALUE_PACK_APPLICATION_REPORT_NAME,
    VALUE_PACK_NAME,
    apply_and_write_pilot_input_value_pack,
)
from experiments.pilot_input_value_pack_sheet import (
    FILL_SHEET_NAME,
    IMPORT_REPORT_NAME,
    import_and_write_pilot_input_value_pack_fill_sheet,
)
from experiments.pilot_input_value_pack_status import (
    STATUS_MARKDOWN_NAME,
    STATUS_REPORT_NAME,
    write_pilot_input_value_pack_status,
)


P0_INPUT_FREEZE_REPORT_NAME = "pilot_p0_input_freeze_report.json"
P0_INPUT_FREEZE_MARKDOWN_NAME = "pilot_p0_input_freeze_report.md"


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _gate_from_report(
    *,
    gate_id: str,
    gate_name: str,
    report_path: Path,
    report: dict[str, Any] | None,
    skipped_reason: str | None = None,
) -> dict[str, Any]:
    """把单个子报告转换为统一 gate 行。"""
    if skipped_reason is not None:
        return {
            "gate_id": gate_id,
            "gate_name": gate_name,
            "status": "skipped",
            "report_path": str(report_path),
            "reason": skipped_reason,
        }
    if report is None:
        return {
            "gate_id": gate_id,
            "gate_name": gate_name,
            "status": "fail",
            "report_path": str(report_path),
            "reason": "missing_report_payload",
        }
    decision = report.get("overall_decision")
    return {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "status": "pass" if decision == "pass" else "fail",
        "report_path": str(report_path),
        "overall_decision": decision,
        "recommended_next_stage": report.get("recommended_next_stage"),
        "summary": report.get("summary", {}),
    }


def _first_blocking_gate(gates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """返回第一个未通过或被跳过的 gate。"""
    for gate in gates:
        if gate["status"] != "pass":
            return gate
    return None


def run_pilot_p0_input_freeze(
    *,
    workspace_root: str | Path,
    value_pack_path: str | Path | None = None,
    fill_sheet_path: str | Path | None = None,
) -> dict[str, Any]:
    """运行 P0 输入冻结聚合门禁并写出所有子报告。

    执行顺序是:
    1. 导入 CSV 填写表。
    2. 校验 value pack 填写状态。
    3. 只有前两步通过时才应用 value pack。
    4. 应用通过后重新运行输入模板预检。
    5. 最后生成 execution readiness 报告。
    """
    workspace = Path(workspace_root)
    value_pack = Path(value_pack_path) if value_pack_path is not None else workspace / VALUE_PACK_NAME
    fill_sheet = Path(fill_sheet_path) if fill_sheet_path is not None else workspace / FILL_SHEET_NAME

    import_report_path = workspace / IMPORT_REPORT_NAME
    status_report_path = workspace / STATUS_REPORT_NAME
    status_markdown_path = workspace / STATUS_MARKDOWN_NAME
    application_report_path = workspace / VALUE_PACK_APPLICATION_REPORT_NAME
    preflight_report_path = workspace / PREFLIGHT_REPORT_NAME
    readiness_report_path = workspace / EXECUTION_READINESS_REPORT_NAME

    import_report = import_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack,
        input_csv_path=fill_sheet,
        output_value_pack_path=None,
        report_path=import_report_path,
    )
    status_report = write_pilot_input_value_pack_status(
        workspace_root=workspace,
        value_pack_path=value_pack,
        output_json_path=status_report_path,
        output_markdown_path=status_markdown_path,
    )

    gates = [
        _gate_from_report(
            gate_id="p0_csv_import",
            gate_name="CSV value_json 导入",
            report_path=import_report_path,
            report=import_report,
        ),
        _gate_from_report(
            gate_id="p0_value_pack_status",
            gate_name="value pack 填写状态校验",
            report_path=status_report_path,
            report=status_report,
        ),
    ]

    can_apply = import_report.get("overall_decision") == "pass" and status_report.get("overall_decision") == "pass"
    if can_apply:
        application_report = apply_and_write_pilot_input_value_pack(
            workspace_root=workspace,
            value_pack_path=value_pack,
            report_path=application_report_path,
        )
    else:
        application_report = None
    gates.append(
        _gate_from_report(
            gate_id="p0_value_pack_application",
            gate_name="value pack 应用",
            report_path=application_report_path,
            report=application_report,
            skipped_reason=None if can_apply else "csv_import_or_value_pack_status_failed",
        )
    )

    can_preflight = application_report is not None and application_report.get("overall_decision") == "pass"
    if can_preflight:
        preflight_report = write_pilot_input_plan_preflight_report(
            workspace_root=workspace,
            output_path=preflight_report_path,
        )
    else:
        preflight_report = None
    gates.append(
        _gate_from_report(
            gate_id="p0_input_plan_preflight",
            gate_name="输入模板预检",
            report_path=preflight_report_path,
            report=preflight_report,
            skipped_reason=None if can_preflight else "value_pack_application_not_passed",
        )
    )

    can_readiness = preflight_report is not None and preflight_report.get("overall_decision") == "pass"
    if can_readiness:
        readiness_report = write_pilot_execution_readiness_report(
            workspace_root=workspace,
            output_path=readiness_report_path,
        )
    else:
        readiness_report = None
    gates.append(
        _gate_from_report(
            gate_id="p0_execution_readiness",
            gate_name="执行就绪门禁",
            report_path=readiness_report_path,
            report=readiness_report,
            skipped_reason=None if can_readiness else "input_plan_preflight_not_passed",
        )
    )

    first_blocking = _first_blocking_gate(gates)
    decision = "pass" if first_blocking is None else "fail"
    return {
        "artifact_name": P0_INPUT_FREEZE_REPORT_NAME,
        "workspace_root": str(workspace),
        "value_pack_path": str(value_pack),
        "fill_sheet_path": str(fill_sheet),
        "overall_decision": decision,
        "recommended_next_stage": "image_generation_launch_plan" if decision == "pass" else "fix_p0_input_freeze",
        "first_blocking_gate": first_blocking,
        "gates": gates,
        "summary": {
            "gate_count": len(gates),
            "pass_count": sum(1 for gate in gates if gate["status"] == "pass"),
            "fail_count": sum(1 for gate in gates if gate["status"] == "fail"),
            "skipped_count": sum(1 for gate in gates if gate["status"] == "skipped"),
        },
    }


def render_pilot_p0_input_freeze_markdown(report: dict[str, Any]) -> str:
    """把 P0 输入冻结报告渲染为 Markdown。"""
    lines = [
        "# pilot P0 输入冻结聚合门禁报告",
        "",
        f"- 工作区: `{report['workspace_root']}`",
        f"- value pack: `{report['value_pack_path']}`",
        f"- CSV 填写表: `{report['fill_sheet_path']}`",
        f"- 总体结论: `{report['overall_decision']}`",
        f"- 推荐下一阶段: `{report['recommended_next_stage']}`",
        "",
        "## 汇总",
        "",
        "```text",
        f"gate_count = {report['summary']['gate_count']}",
        f"pass_count = {report['summary']['pass_count']}",
        f"fail_count = {report['summary']['fail_count']}",
        f"skipped_count = {report['summary']['skipped_count']}",
        "```",
        "",
        "## 门禁明细",
        "",
        "| 顺序 | gate_id | 状态 | 报告 | 说明 |",
        "|---:|---|---|---|---|",
    ]
    for index, gate in enumerate(report.get("gates", []), start=1):
        note = gate.get("reason") or gate.get("recommended_next_stage") or "-"
        lines.append(
            f"| {index} | `{gate['gate_id']}` | `{gate['status']}` | `{gate['report_path']}` | {note} |"
        )
    first = report.get("first_blocking_gate")
    if first:
        lines.extend(
            [
                "",
                "## 第一个阻断门禁",
                "",
                "```text",
                f"gate_id = {first.get('gate_id')}",
                f"status = {first.get('status')}",
                f"reason = {first.get('reason', first.get('recommended_next_stage', '-'))}",
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def write_pilot_p0_input_freeze_report(
    *,
    workspace_root: str | Path,
    value_pack_path: str | Path | None,
    fill_sheet_path: str | Path | None,
    output_json_path: str | Path,
    output_markdown_path: str | Path,
) -> dict[str, Any]:
    """运行并写出 P0 输入冻结聚合门禁报告。"""
    report = run_pilot_p0_input_freeze(
        workspace_root=workspace_root,
        value_pack_path=value_pack_path,
        fill_sheet_path=fill_sheet_path,
    )
    _write_json(output_json_path, report)
    markdown_path = Path(output_markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_pilot_p0_input_freeze_markdown(report), encoding="utf-8")
    return report
