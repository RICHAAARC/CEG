"""真实 pilot 输入执行就绪聚合报告。

该模块把输入计划 preflight、替换清单和值包应用报告聚合成一个启动判断。
它不运行真实图像生成, 只回答“当前是否可以安全进入真实 SD / watermark
pilot”。该设计可以避免单独查看多个 JSON 报告时误判阶段状态。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXECUTION_READINESS_REPORT_NAME = "pilot_execution_readiness_report.json"


REQUIRED_REPORT_FILES = {
    "preflight_report": "pilot_input_plan_preflight_report.json",
    "replacement_checklist": "pilot_input_plan_replacement_checklist.json",
    "value_pack_application_report": "pilot_input_value_pack_application_report.json",
}


def _read_json(path: Path) -> dict[str, Any]:
    """读取 JSON 报告。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _report_gate(name: str, path: Path, expected_pass: bool) -> dict[str, Any]:
    """读取单个报告并转换为统一 gate 结构。"""
    if not path.is_file():
        return {
            "gate_name": name,
            "status": "fail",
            "path": str(path),
            "reason": "missing_report",
        }

    try:
        payload = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "gate_name": name,
            "status": "fail",
            "path": str(path),
            "reason": f"unreadable_json: {exc}",
        }

    decision = payload.get("overall_decision")
    if expected_pass:
        status = "pass" if decision == "pass" else "fail"
    else:
        status = "pass" if decision in {"pass", "fail"} else "fail"

    return {
        "gate_name": name,
        "status": status,
        "path": str(path),
        "observed_decision": decision,
        "summary": payload.get("summary", {}),
    }


def build_pilot_execution_readiness_report(*, workspace_root: str | Path) -> dict[str, Any]:
    """生成真实 pilot 执行就绪报告。"""
    root = Path(workspace_root)
    preflight_gate = _report_gate(
        "pilot_input_plan_preflight",
        root / REQUIRED_REPORT_FILES["preflight_report"],
        expected_pass=True,
    )
    replacement_gate = _report_gate(
        "pilot_input_plan_replacement_checklist",
        root / REQUIRED_REPORT_FILES["replacement_checklist"],
        expected_pass=False,
    )
    value_pack_gate = _report_gate(
        "pilot_input_value_pack_application",
        root / REQUIRED_REPORT_FILES["value_pack_application_report"],
        expected_pass=True,
    )

    gates = [preflight_gate, replacement_gate, value_pack_gate]
    blocking_gates = [gate for gate in gates if gate["status"] != "pass"]

    # replacement checklist 是诊断辅助文件, 它可以为 fail, 因为真实值应用后可能不再需要重新生成。
    # 真正决定能否启动真实图像生成的是 preflight 和 value pack application 必须为 pass。
    strict_gates = [preflight_gate, value_pack_gate]
    strict_blocking = [gate for gate in strict_gates if gate["status"] != "pass"]
    overall_decision = "pass" if not strict_blocking else "fail"

    return {
        "artifact_name": EXECUTION_READINESS_REPORT_NAME,
        "workspace_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": (
            "real_image_generation_pilot"
            if overall_decision == "pass"
            else "complete_value_pack_and_rerun_preflight"
        ),
        "gates": gates,
        "blocking_gates": strict_blocking,
        "summary": {
            "gate_count": len(gates),
            "strict_gate_count": len(strict_gates),
            "blocking_gate_count": len(strict_blocking),
            "diagnostic_gate_issue_count": len(blocking_gates),
        },
    }


def write_pilot_execution_readiness_report(
    *,
    workspace_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """写出真实 pilot 执行就绪报告。"""
    report = build_pilot_execution_readiness_report(workspace_root=workspace_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
