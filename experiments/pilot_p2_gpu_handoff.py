"""构建 P2 图像生成 GPU 交接清单。

该模块的作用是把已经通过的 P0 / P1 报告转换为一个可重复生成的 Colab GPU
执行清单。它不运行 SD 模型, 不生成图像, 也不写入任何密钥。这样做属于通用
工程写法: 对需要外部算力执行的阶段生成显式输入、输出、验收和安全边界。

项目特定写法是: 该清单固定对齐 CEG P2 图像生成输出契约, 包括
`prompt_plan.json`、`image_pairs.json` 和 image manifests。后续只有这些真实
GPU 产物通过接收门禁后, 才能进入 P3 attack。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from experiments.image_generation_plan import REQUIRED_EXTERNAL_OUTPUTS
from experiments.pilot_image_generation_launch_plan import (
    IMAGE_GENERATION_COMMAND_PLAN_NAME,
    LAUNCH_PLAN_REPORT_NAME,
)
from experiments.pilot_p0_input_freeze import P0_INPUT_FREEZE_REPORT_NAME


P2_GPU_HANDOFF_DIR = Path("gpu_handoff") / "p2_image_generation"
P2_GPU_HANDOFF_CHECKLIST_NAME = "p2_image_generation_colab_execution_checklist.json"
P2_GPU_HANDOFF_RUNBOOK_NAME = "p2_image_generation_colab_runbook.md"
P2_OUTPUT_ACCEPTANCE_REPORT_NAME = "pilot_image_generation_output_acceptance_report.json"


def _read_json(path: Path) -> dict[str, Any]:
    """读取 JSON 对象, 并在类型不匹配时给出明确错误。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_status(path: Path) -> dict[str, Any]:
    """读取阶段报告的关键状态, 缺失或不可读时返回 fail。"""
    if not path.is_file():
        return {"path": str(path), "overall_decision": "fail", "reason": "missing_report"}
    try:
        payload = _read_json(path)
    except Exception as exc:  # pragma: no cover - 具体错误来自底层 JSON 或 IO
        return {"path": str(path), "overall_decision": "fail", "reason": f"unreadable_report: {exc}"}
    return {
        "path": str(path),
        "overall_decision": payload.get("overall_decision"),
        "recommended_next_stage": payload.get("recommended_next_stage"),
        "summary": payload.get("summary", {}),
    }


def _load_command_plan(path: Path) -> list[dict[str, Any]]:
    """读取 P1 物化出的图像生成命令计划。"""
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _required_output_rows(output_root: Path) -> list[dict[str, str]]:
    """构造 P2 必需输出路径列表。"""
    rows = [
        {
            "relative_path": relative,
            "absolute_path": str(output_root / relative),
            "purpose": "P2 接收门禁的显式必需文件",
        }
        for relative in REQUIRED_EXTERNAL_OUTPUTS
    ]
    rows.extend(
        [
            {
                "relative_path": "clean/*",
                "absolute_path": str(output_root / "clean"),
                "purpose": "真实 clean 图像目录, 由 image_pairs.json 中 clean_image_path 或 reference_path 引用",
            },
            {
                "relative_path": "watermarked/*",
                "absolute_path": str(output_root / "watermarked"),
                "purpose": "真实 watermarked 图像目录, 由 image_pairs.json 中 watermarked_image_path 或 watermarked_path 引用",
            },
        ]
    )
    return rows


def build_p2_image_generation_gpu_handoff_checklist(
    *,
    workspace_root: str | Path,
    handoff_root: str | Path | None = None,
) -> dict[str, Any]:
    """构建 P2 Colab GPU 执行清单。

    该函数只读取 P0 / P1 报告和命令计划, 不执行外部命令。它的返回值用于告诉
    用户在 Colab 中需要确认哪些输入、运行哪些命令、回传哪些文件。
    """
    workspace = Path(workspace_root)
    handoff = Path(handoff_root) if handoff_root is not None else workspace / P2_GPU_HANDOFF_DIR
    p0_report = workspace / P0_INPUT_FREEZE_REPORT_NAME
    p1_report = workspace / LAUNCH_PLAN_REPORT_NAME
    command_plan_path = workspace / IMAGE_GENERATION_COMMAND_PLAN_NAME
    output_root = workspace / "inputs" / "images"
    p0_status = _report_status(p0_report)
    p1_status = _report_status(p1_report)
    command_plan = _load_command_plan(command_plan_path)
    blocking_items: list[dict[str, str]] = []
    if p0_status.get("overall_decision") != "pass":
        blocking_items.append({"gate": "p0_input_freeze", "reason": "p0_report_not_pass"})
    if p1_status.get("overall_decision") != "pass":
        blocking_items.append({"gate": "p1_image_generation_launch_plan", "reason": "p1_report_not_pass"})
    if not command_plan:
        blocking_items.append({"gate": "image_generation_command_plan", "reason": "missing_or_empty_command_plan"})

    return {
        "artifact_name": P2_GPU_HANDOFF_CHECKLIST_NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace),
        "handoff_root": str(handoff),
        "stage": "p2_image_generation_outputs",
        "overall_decision": "ready_for_user_colab_gpu_execution" if not blocking_items else "fail",
        "local_execution_status": "pause_required_no_local_gpu",
        "secret_handling": {
            "requires_huggingface_token": True,
            "allowed_environment_variables": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
            "forbidden_storage": [
                "不要把 token 写入仓库文件",
                "不要把 token 写入 CSV",
                "不要把 token 写入 manifest",
                "不要把 token 打印到 notebook 输出或日志",
            ],
        },
        "preconditions": {
            "p0_input_freeze": p0_status,
            "p1_image_generation_launch_plan": p1_status,
            "command_plan_path": str(command_plan_path),
            "command_count": len(command_plan),
        },
        "colab_path_mapping": {
            "windows_workspace_root": str(workspace),
            "colab_workspace_root": "/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500",
            "output_root": "/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images",
        },
        "command_plan": command_plan,
        "required_outputs": _required_output_rows(output_root),
        "acceptance_commands": [
            (
                "python scripts/validate_pilot_image_generation_outputs.py "
                "--output-root D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/inputs/images "
                "--out D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500/"
                f"{P2_OUTPUT_ACCEPTANCE_REPORT_NAME} --require-pass"
            ),
            (
                "python scripts/build_pilot_stage_progress_summary.py "
                "--workspace D:/content/drive/MyDrive/CEG/pilot_runs/real_pilot_input_workspace_20260617_034500"
            ),
        ],
        "blocking_items": blocking_items,
        "notes": [
            "该清单不代表 P2 已完成, 只代表可以交给用户在 Colab GPU 环境执行。",
            "P2 正式证据必须来自真实 clean / watermarked 图像和 manifests。",
            "如果 Colab 中不使用 command_plan, 也必须产出 required_outputs 中列出的同名文件。",
        ],
    }


def render_p2_image_generation_gpu_handoff_runbook(checklist: dict[str, Any]) -> str:
    """把 P2 GPU 交接清单渲染为 Markdown runbook。"""
    lines = [
        "# P2 图像生成 Colab GPU 执行清单",
        "",
        "## 1. 当前结论",
        "",
        f"- 阶段: `{checklist['stage']}`",
        f"- 清单状态: `{checklist['overall_decision']}`",
        f"- 本地执行状态: `{checklist['local_execution_status']}`",
        "",
        "该文件只用于指导 Colab GPU 执行, 不包含 Hugging Face token, 也不表示 P2 已完成。",
        "",
        "## 2. 密钥边界",
        "",
        "- 允许在 Colab 环境变量中提供 `HF_TOKEN` 或 `HUGGING_FACE_HUB_TOKEN`。",
        "- 禁止把 token 写入仓库、CSV、manifest、Notebook 输出或日志。",
        "",
        "## 3. 前置门禁",
        "",
        "```text",
        f"P0 = {checklist['preconditions']['p0_input_freeze'].get('overall_decision')}",
        f"P1 = {checklist['preconditions']['p1_image_generation_launch_plan'].get('overall_decision')}",
        f"command_count = {checklist['preconditions']['command_count']}",
        "```",
        "",
        "## 4. Colab 路径映射",
        "",
        "```text",
        f"workspace = {checklist['colab_path_mapping']['colab_workspace_root']}",
        f"output_root = {checklist['colab_path_mapping']['output_root']}",
        "```",
        "",
        "## 5. 必须回传的 P2 输出",
        "",
        "| 序号 | 相对路径 | 用途 |",
        "|---:|---|---|",
    ]
    for index, row in enumerate(checklist.get("required_outputs", []), start=1):
        lines.append(f"| {index} | `{row['relative_path']}` | {row['purpose']} |")
    lines.extend(["", "## 6. 接收验收命令", "", "```text"])
    lines.extend(str(command) for command in checklist.get("acceptance_commands", []))
    lines.extend(["```", "", "## 7. 禁止事项", ""])
    lines.extend(
        [
            "1. 不能用 mock 图像替代真实 P2 图像。",
            "2. 不能跳过 `prompt_plan.json`、`image_pairs.json` 或 image manifests。",
            "3. 不能把 P3 attack 输出混入 P2 图像生成目录。",
            "4. 不能手工声明 P2 通过, 必须运行接收验收命令。",
            "",
        ]
    )
    return "\n".join(lines)


def write_p2_image_generation_gpu_handoff(
    *,
    workspace_root: str | Path,
    handoff_root: str | Path | None = None,
) -> dict[str, Any]:
    """写出 P2 GPU 交接 JSON 清单和 Markdown runbook。"""
    checklist = build_p2_image_generation_gpu_handoff_checklist(
        workspace_root=workspace_root,
        handoff_root=handoff_root,
    )
    handoff = Path(checklist["handoff_root"])
    _write_json(handoff / P2_GPU_HANDOFF_CHECKLIST_NAME, checklist)
    (handoff / P2_GPU_HANDOFF_RUNBOOK_NAME).write_text(
        render_p2_image_generation_gpu_handoff_runbook(checklist),
        encoding="utf-8",
    )
    return checklist
