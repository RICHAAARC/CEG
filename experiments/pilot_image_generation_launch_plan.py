"""真实图像生成 pilot 启动计划。

该模块只生成外部图像生成命令计划, 不直接执行 SD 或 watermark backend。它要求
`pilot_execution_readiness_report.json` 先通过, 再根据 launch variables 和既有
命令模板物化 `run_image_generation_plan.py` 可消费的计划文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.command_templates import materialize_image_generation_command_plan


LAUNCH_VARIABLES_NAME = "pilot_image_generation_launch_variables.draft.json"
LAUNCH_PLAN_REPORT_NAME = "pilot_image_generation_launch_plan_report.json"
IMAGE_GENERATION_COMMAND_PLAN_NAME = "image_generation_command_plan.json"


REQUIRED_VARIABLES = (
    "image_generation_root",
    "prompt_plan_path",
    "output_root",
    "model_config_path",
    "external_backend_command_json_path",
)


def _read_json(path: str | Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_launch_variables_template(*, workspace_root: str | Path) -> dict[str, Any]:
    """生成外部图像生成启动变量草稿。"""
    root = Path(workspace_root)
    return {
        "artifact_name": LAUNCH_VARIABLES_NAME,
        "workspace_root": str(root),
        "manifest_status": "draft_requires_external_backend_paths",
        "image_generation_root_placeholder": "replace_with_external_image_generation_project_root",
        "prompt_plan_path": str(root / "inputs" / "prompts" / "prompt_plan.draft.json"),
        "output_root": str(root / "inputs" / "images"),
        "model_config_path": str(root / "configs" / "model_config.draft.json"),
        "external_backend_command_json_path": str(root / "configs" / "p2_external_backend_command.draft.json"),
        "instructions": [
            "把 image_generation_root_placeholder 替换为 image_generation_root.",
            "确认 prompt_plan_path、output_root 和 model_config_path 均指向真实 pilot 工作区文件.",
            "执行前必须先让 pilot_execution_readiness_report.json 为 pass.",
            "正式 Colab 执行前必须把 p2_external_backend_command.draft.json 中的 external_command_placeholder 替换为 external_command.",
        ],
    }


def write_launch_variables_template(*, workspace_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    """写出外部图像生成启动变量草稿。"""
    payload = build_launch_variables_template(workspace_root=workspace_root)
    _write_json(output_path, payload)
    return payload


def _normalize_launch_variables(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """把启动变量草稿转换为模板变量, 并收集阻断项。"""
    blocking: list[dict[str, str]] = []
    variables: dict[str, Any] = {}
    for key in REQUIRED_VARIABLES:
        placeholder_key = f"{key}_placeholder"
        if key in payload:
            value = payload[key]
        elif placeholder_key in payload:
            value = payload[placeholder_key]
            blocking.append({"field": placeholder_key, "reason": "placeholder_key_not_replaced"})
        else:
            value = None
            blocking.append({"field": key, "reason": "missing_required_variable"})
        if isinstance(value, str) and ("replace_with" in value or "placeholder" in value):
            blocking.append({"field": key, "reason": "placeholder_value_not_replaced"})
        variables[key] = value
    return variables, blocking


def build_pilot_image_generation_launch_plan(
    *,
    workspace_root: str | Path,
    readiness_report_path: str | Path,
    launch_variables_path: str | Path,
    template_path: str | Path,
) -> dict[str, Any]:
    """生成真实图像生成 pilot 启动计划报告。"""
    readiness = _read_json(readiness_report_path)
    launch_variables = _read_json(launch_variables_path)
    variables, blocking_items = _normalize_launch_variables(launch_variables)

    if readiness.get("overall_decision") != "pass":
        blocking_items.append(
            {
                "field": "pilot_execution_readiness_report",
                "reason": "execution_readiness_not_pass",
            }
        )

    command_plan: list[dict[str, Any]] = []
    if not blocking_items:
        specs = materialize_image_generation_command_plan(template_path, variables)
        command_plan = [spec.to_dict() for spec in specs]

    return {
        "artifact_name": LAUNCH_PLAN_REPORT_NAME,
        "workspace_root": str(Path(workspace_root)),
        "readiness_report_path": str(readiness_report_path),
        "launch_variables_path": str(launch_variables_path),
        "template_path": str(template_path),
        "overall_decision": "pass" if not blocking_items else "fail",
        "recommended_next_stage": (
            "run_image_generation_command_plan"
            if not blocking_items
            else "complete_execution_readiness_and_launch_variables"
        ),
        "blocking_items": blocking_items,
        "command_plan": command_plan,
        "summary": {
            "blocking_item_count": len(blocking_items),
            "command_count": len(command_plan),
        },
    }


def write_pilot_image_generation_launch_plan(
    *,
    workspace_root: str | Path,
    readiness_report_path: str | Path,
    launch_variables_path: str | Path,
    template_path: str | Path,
    report_path: str | Path,
    command_plan_path: str | Path | None = None,
) -> dict[str, Any]:
    """写出启动计划报告, 并在通过时可选写出命令计划。"""
    report = build_pilot_image_generation_launch_plan(
        workspace_root=workspace_root,
        readiness_report_path=readiness_report_path,
        launch_variables_path=launch_variables_path,
        template_path=template_path,
    )
    _write_json(report_path, report)
    if command_plan_path is not None and report["overall_decision"] == "pass":
        _write_json(command_plan_path, report["command_plan"])
    return report
