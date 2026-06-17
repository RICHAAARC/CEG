"""P2 通过后的 P3 / P4 接续计划。

该模块只生成接续命令和风险提示, 不运行 attack、detection 或统计流程。它的作用是让用户
在 Colab GPU 生成真实图像并通过 P2 接收门禁后, 可以按同一工作区继续执行 attack 和
检测输入生成, 同时明确哪些输出仍不能被声明为正式论文结论。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

PLAN_NAME = "pilot_post_p2_resume_plan.json"
RUNBOOK_NAME = "pilot_post_p2_resume_runbook.md"
P2_REPORT_NAME = "pilot_image_generation_output_acceptance_report.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    """读取 JSON 对象, 缺失或不可读时返回 None。"""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _path_text(path: Path) -> str:
    """把路径转换为命令中使用的正斜杠文本。"""
    return str(path).replace("\\", "/")


def _command_row(stage_id: str, description: str, command: list[str], *, requires_previous_pass: str | None) -> dict[str, Any]:
    """构造一条接续命令记录。"""
    return {
        "stage_id": stage_id,
        "description": description,
        "requires_previous_pass": requires_previous_pass,
        "command": command,
        "shell_command": " ".join(command),
    }


def build_post_p2_resume_plan(*, workspace_root: str | Path) -> dict[str, Any]:
    """构造 P2 通过后的 P3 / P4 接续计划。"""
    workspace = Path(workspace_root)
    p2_report = _read_json(workspace / P2_REPORT_NAME)
    p2_pass = bool(p2_report and p2_report.get("overall_decision") == "pass")
    images_root = workspace / "inputs" / "images"
    attack_root = workspace / "image_attacks"
    detection_root = workspace / "detection_outputs"
    commands = [
        _command_row(
            "p3_attack_run",
            "基于 P2 image_pairs.json 运行轻量 attack workflow, 生成 attacked 图像与 attack manifests。",
            [
                "python",
                "scripts/run_image_attack_workflow.py",
                "--image-pairs",
                _path_text(images_root / "image_pairs.json"),
                "--out",
                _path_text(attack_root),
                "--attack-families",
                "brightness_contrast,gaussian_noise",
            ],
            requires_previous_pass="p2_image_generation_outputs",
        ),
        _command_row(
            "p3_attack_acceptance",
            "校验 attack 输出是否可进入 detection。",
            [
                "python",
                "scripts/validate_pilot_attack_outputs.py",
                "--output-root",
                _path_text(attack_root),
                "--out",
                _path_text(workspace / "pilot_attack_output_acceptance_report.json"),
                "--require-pass",
            ],
            requires_previous_pass="p3_attack_run",
        ),
        _command_row(
            "p4_detection_producer",
            "从 image_pairs 和 attacked_image_manifest 生成 CEG detection 事件契约输入。",
            [
                "python",
                "scripts/run_ceg_detection_producer.py",
                "--image-pairs",
                _path_text(images_root / "image_pairs.json"),
                "--attacked-image-manifest",
                _path_text(attack_root / "image_manifests" / "attacked_image_manifest.json"),
                "--out",
                _path_text(detection_root),
            ],
            requires_previous_pass="p3_attack_acceptance",
        ),
        _command_row(
            "p4_detection_acceptance",
            "校验 detection events / thresholds / manifest 是否满足 fixed-FPR 统计前置契约。",
            [
                "python",
                "scripts/validate_pilot_detection_outputs.py",
                "--output-root",
                _path_text(detection_root),
                "--out",
                _path_text(workspace / "pilot_detection_output_acceptance_report.json"),
                "--require-pass",
            ],
            requires_previous_pass="p4_detection_producer",
        ),
        _command_row(
            "stage_progress_refresh",
            "刷新整体阶段进度摘要。",
            [
                "python",
                "scripts/build_pilot_stage_progress_summary.py",
                "--workspace",
                _path_text(workspace),
            ],
            requires_previous_pass=None,
        ),
    ]
    warnings: list[dict[str, str]] = []
    if not p2_pass:
        warnings.append(
            {
                "warning_type": "p2_not_passed_yet",
                "message": "P2 图像生成接收门禁尚未通过, 本计划只能作为 GPU 回传后的接续预案, 现在不能执行 P3/P4。",
            }
        )
    warnings.append(
        {
            "warning_type": "detection_producer_is_contract_dry_run",
            "message": "run_ceg_detection_producer.py 只生成检测事件契约 dry-run, 不等价于正式检测模型结果。",
        }
    )
    warnings.append(
        {
            "warning_type": "fixed_fpr_roles_may_still_be_missing",
            "message": "若 P2 image_pairs 未覆盖 calibration clean negative、test clean negative 和 test positive, P4/P7 仍会阻断。",
        }
    )
    return {
        "artifact_name": PLAN_NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace),
        "overall_decision": "ready_after_p2_pass" if p2_pass else "blocked_until_p2_pass",
        "p2_report_path": str(workspace / P2_REPORT_NAME),
        "p2_overall_decision": p2_report.get("overall_decision") if p2_report else None,
        "command_rows": commands,
        "execution_warnings": warnings,
        "required_manual_boundary": [
            "不能在 P2 失败时执行 P3/P4 并声明论文结果。",
            "不能把 detection contract dry-run 声明为正式检测模型结果。",
            "不能跳过 attack 输出接收门禁。",
        ],
        "summary": {
            "command_count": len(commands),
            "warning_count": len(warnings),
            "p2_passed": p2_pass,
        },
    }


def render_post_p2_resume_runbook(plan: dict[str, Any]) -> str:
    """渲染 P2 后接续计划 Markdown。"""
    lines = [
        "# P2 通过后的 P3 / P4 接续计划",
        "",
        "## 1. 当前结论",
        "",
        f"- 状态: `{plan['overall_decision']}`",
        f"- P2 报告结论: `{plan.get('p2_overall_decision')}`",
        "",
        "该文件只说明 P2 通过后如何继续, 不代表 attack、detection 或 TPR@FPR 已完成。",
        "",
        "## 2. 执行警告",
        "",
    ]
    for warning in plan.get("execution_warnings", []):
        lines.append(f"- `{warning['warning_type']}`: {warning['message']}")
    lines.extend(["", "## 3. 接续命令", ""])
    for index, row in enumerate(plan.get("command_rows", []), start=1):
        lines.extend(
            [
                f"### 3.{index} {row['stage_id']}",
                "",
                row["description"],
                "",
                "```text",
                row["shell_command"],
                "```",
                "",
            ]
        )
    lines.extend(["## 4. 禁止事项", ""])
    for item in plan.get("required_manual_boundary", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_post_p2_resume_plan(*, workspace_root: str | Path, out_root: str | Path | None = None) -> dict[str, Any]:
    """写出 P2 后接续计划 JSON 和 Markdown。"""
    workspace = Path(workspace_root)
    output_root = Path(out_root) if out_root is not None else workspace / "gpu_handoff" / "post_p2_resume"
    plan = build_post_p2_resume_plan(workspace_root=workspace)
    _write_json(output_root / PLAN_NAME, plan)
    (output_root / RUNBOOK_NAME).write_text(render_post_p2_resume_runbook(plan), encoding="utf-8")
    return plan
