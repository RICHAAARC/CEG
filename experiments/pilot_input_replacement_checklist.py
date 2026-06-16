"""把 pilot 输入计划预检失败项转换为可执行替换清单。

该模块不生成真实实验数据, 只把 preflight 报告中的占位字段整理为人工或
外部 runner 可以逐项填写的任务列表。这样可以把“预检失败”从一个诊断结果
推进为下一步真实 pilot 输入准备的操作清单。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPLACEMENT_CHECKLIST_NAME = "pilot_input_plan_replacement_checklist.json"


FIELD_GUIDANCE = {
    "prompt_text_placeholder": {
        "replacement_key": "prompt_text",
        "expected_content": "真实 prompt 文本, 用于生成 clean / watermarked 图像.",
    },
    "prompt_family_placeholder": {
        "replacement_key": "prompt_family",
        "expected_content": "prompt 类别, 例如 object_scene、portrait、landscape 或 text_rendering.",
    },
    "license_note_placeholder": {
        "replacement_key": "license_note",
        "expected_content": "prompt 来源、许可说明或人工编写说明.",
    },
    "split_placeholder": {
        "replacement_key": "split",
        "expected_content": "calibration 或 test. calibration 只用于阈值选择, test 用于最终评估.",
    },
    "sample_role_placeholder": {
        "replacement_key": "sample_role",
        "expected_content": "clean_negative、positive_source 或 attacked_positive 等样本角色.",
    },
    "seed_placeholder": {
        "replacement_key": "seed",
        "expected_content": "整数随机种子, 用于复现实验图像.",
    },
    "seed_role_placeholder": {
        "replacement_key": "seed_role",
        "expected_content": "primary 或 replicate, 用于区分主种子和重复实验种子.",
    },
    "backend_type_placeholder": {
        "replacement_key": "backend_type",
        "expected_content": "diffusers、external_command 或其他受控生成 backend 类型.",
    },
    "model_id_placeholder": {
        "replacement_key": "model_id",
        "expected_content": "真实 SD 模型 ID、本地路径或外部生成服务标识.",
    },
    "scheduler_placeholder": {
        "replacement_key": "scheduler",
        "expected_content": "真实采样调度器名称, 例如 ddim、euler 或 dpm_solver.",
    },
    "num_inference_steps_placeholder": {
        "replacement_key": "num_inference_steps",
        "expected_content": "正整数采样步数.",
    },
    "guidance_scale_placeholder": {
        "replacement_key": "guidance_scale",
        "expected_content": "数值型 classifier-free guidance scale.",
    },
    "image_size_placeholder": {
        "replacement_key": "image_size",
        "expected_content": "图像尺寸, 建议使用 [width, height] 形式.",
    },
    "requires_huggingface_token_placeholder": {
        "replacement_key": "requires_huggingface_token",
        "expected_content": "布尔值, 表示该模型下载或运行是否需要 Hugging Face token.",
    },
    "watermark_method_placeholder": {
        "replacement_key": "watermark_method",
        "expected_content": "真实水印方法名称, 例如 ceg 或外部 baseline 方法名.",
    },
    "payload_bits_placeholder": {
        "replacement_key": "payload_bits",
        "expected_content": "payload bit 串或 payload 生成规则.",
    },
    "watermark_strength_placeholder": {
        "replacement_key": "watermark_strength",
        "expected_content": "水印嵌入强度或方法特定嵌入参数.",
    },
    "backend_command_placeholder": {
        "replacement_key": "backend_command",
        "expected_content": "外部 backend 命令. 若不使用外部命令, 应写入明确的内部 backend 标识.",
    },
    "evidence_path_placeholder": {
        "replacement_key": "evidence_path",
        "expected_content": "backend 日志、运行 manifest 或其他可复核证据路径.",
    },
}


def _load_json(path: str | Path) -> dict[str, Any]:
    """读取 JSON 文件并返回字典。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _replacement_task_from_finding(finding: dict[str, Any]) -> dict[str, Any] | None:
    """把一个 placeholder_key finding 转换为替换任务。"""
    if finding.get("finding_type") != "placeholder_key":
        return None

    placeholder_key = str(finding["evidence"])
    guidance = FIELD_GUIDANCE.get(
        placeholder_key,
        {
            "replacement_key": placeholder_key.removesuffix("_placeholder"),
            "expected_content": "真实实验配置值, 且字段名不得继续使用 _placeholder 后缀.",
        },
    )
    return {
        "task_id": f"replace_{placeholder_key}",
        "file_key": finding["file_key"],
        "relative_path": finding["relative_path"],
        "json_path": finding["json_path"],
        "placeholder_key": placeholder_key,
        "replacement_key": guidance["replacement_key"],
        "expected_content": guidance["expected_content"],
        "blocking_reason": "该字段仍是占位字段, 不能启动真实 SD / watermark pilot.",
    }


def build_pilot_input_replacement_checklist(*, preflight_report_path: str | Path) -> dict[str, Any]:
    """基于 preflight 报告生成真实输入替换清单。"""
    report = _load_json(preflight_report_path)
    replacement_tasks = [
        task
        for finding in report.get("placeholder_findings", [])
        if (task := _replacement_task_from_finding(finding)) is not None
    ]
    missing_file_tasks = [
        {
            "task_id": f"create_{item['file_key']}",
            "file_key": item["file_key"],
            "relative_path": item["relative_path"],
            "expected_content": "创建该必需计划文件, 并写入真实 pilot 输入配置.",
            "blocking_reason": "缺少必需计划文件, 无法验证真实 pilot 输入是否完整.",
        }
        for item in report.get("missing_files", [])
    ]
    unreadable_file_tasks = [
        {
            "task_id": f"repair_{item['file_key']}",
            "file_key": item["file_key"],
            "relative_path": item["relative_path"],
            "expected_content": "修复 JSON 格式或编码问题, 使 preflight 可以读取该文件.",
            "blocking_reason": item.get("error", "计划文件不可读取."),
        }
        for item in report.get("unreadable_files", [])
    ]

    blocking_count = len(replacement_tasks) + len(missing_file_tasks) + len(unreadable_file_tasks)
    return {
        "artifact_name": REPLACEMENT_CHECKLIST_NAME,
        "source_preflight_report": str(preflight_report_path),
        "workspace_root": report.get("workspace_root"),
        "overall_decision": "pass" if blocking_count == 0 else "fail",
        "recommended_next_stage": (
            "rerun_pilot_input_plan_preflight"
            if blocking_count
            else report.get("recommended_next_stage", "real_image_generation_pilot")
        ),
        "replacement_tasks": replacement_tasks,
        "missing_file_tasks": missing_file_tasks,
        "unreadable_file_tasks": unreadable_file_tasks,
        "summary": {
            "replacement_task_count": len(replacement_tasks),
            "missing_file_task_count": len(missing_file_tasks),
            "unreadable_file_task_count": len(unreadable_file_tasks),
            "blocking_item_count": blocking_count,
        },
    }


def render_pilot_input_replacement_checklist_markdown(checklist: dict[str, Any]) -> str:
    """把替换清单渲染为人工可读 Markdown。"""
    lines = [
        "# pilot 输入计划占位字段替换清单",
        "",
        "## 1. 结论",
        "",
        "```text",
        f"overall_decision = {checklist['overall_decision']}",
        f"recommended_next_stage = {checklist['recommended_next_stage']}",
        f"replacement_task_count = {checklist['summary']['replacement_task_count']}",
        f"blocking_item_count = {checklist['summary']['blocking_item_count']}",
        "```",
        "",
        "## 2. 替换任务",
        "",
    ]
    if not checklist["replacement_tasks"]:
        lines.append("当前没有占位字段替换任务。")
    else:
        for index, task in enumerate(checklist["replacement_tasks"], start=1):
            lines.extend(
                [
                    f"### 2.{index} {task['task_id']}",
                    "",
                    "```text",
                    f"file = {task['relative_path']}",
                    f"json_path = {task['json_path']}",
                    f"placeholder_key = {task['placeholder_key']}",
                    f"replacement_key = {task['replacement_key']}",
                    f"expected_content = {task['expected_content']}",
                    "```",
                    "",
                ]
            )
    lines.extend(
        [
            "## 3. 下一步",
            "",
            "替换完成后重新运行:",
            "",
            "```text",
            "python scripts/validate_pilot_input_plan_templates.py --workspace <workspace> --require-pass",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_pilot_input_replacement_checklist(
    *,
    preflight_report_path: str | Path,
    output_json_path: str | Path,
    output_markdown_path: str | Path | None = None,
) -> dict[str, Any]:
    """写出 JSON 替换清单, 并可选写出 Markdown 清单。"""
    checklist = build_pilot_input_replacement_checklist(preflight_report_path=preflight_report_path)
    json_path = Path(output_json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(checklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output_markdown_path is not None:
        markdown_path = Path(output_markdown_path)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_pilot_input_replacement_checklist_markdown(checklist), encoding="utf-8")
    return checklist
