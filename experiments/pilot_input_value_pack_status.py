"""汇总并校验真实 pilot 输入 value pack 的填写状态。

该模块只读取 `pilot_input_value_pack.draft.json`, 不自动生成真实 prompt、模型、
水印参数或其他实验值。它的作用是把“还差哪些真实输入”整理为 JSON 和 Markdown,
并在填写完成后检查基本类型和取值是否能进入后续真实 pilot 门禁。

通用工程写法是: 对一个集中式配置填写包做 completeness report 与 schema-like
轻量校验。项目特定写法是: 将 prompt、split、seed、model 和 watermark 字段的
最小运行约束连接到 CEG 的真实 pilot 阶段门禁, 防止把占位值或错误类型误认为
正式实验配置。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.pilot_input_value_pack import PLACEHOLDER_MARKERS, VALUE_PACK_NAME


STATUS_REPORT_NAME = "pilot_input_value_pack_status_report.json"
STATUS_MARKDOWN_NAME = "pilot_input_value_pack_status_report.md"


TYPE_HINT_BY_REPLACEMENT_KEY = {
    "prompt_text": "非空字符串, 建议为真实图像生成 prompt.",
    "prompt_family": "非空字符串, 用于分组统计 prompt 类型.",
    "license_note": "非空字符串, 说明 prompt 来源或授权.",
    "split": "字符串, 必须为 calibration 或 test.",
    "sample_role": "字符串, 必须为 clean_negative、positive_source 或 attacked_positive.",
    "seed": "非负整数, 用于复现图像生成.",
    "seed_role": "字符串, 必须为 primary 或 replicate.",
    "backend_type": "非空字符串, 例如 diffusers、external_command 或受控内部 backend 名称.",
    "model_id": "非空字符串, 为模型 ID、本地路径或外部服务标识.",
    "scheduler": "非空字符串, 为采样调度器名称.",
    "num_inference_steps": "正整数.",
    "guidance_scale": "正数值.",
    "image_size": "长度为2的正整数数组, 例如 [512, 512].",
    "requires_huggingface_token": "布尔值.",
    "watermark_method": "非空字符串, 为 CEG 或外部水印方法名称.",
    "payload_bits": "非空字符串、非空数组或非空对象, 表达 payload 或 payload 规则.",
    "watermark_strength": "数值或非空方法特定参数对象.",
    "backend_command": "非空字符串, 为外部命令或内部 backend 标识.",
    "evidence_path": "非空字符串, 指向 backend 日志或运行 manifest.",
}

ALLOWED_SPLITS = {"calibration", "test"}
ALLOWED_SAMPLE_ROLES = {"clean_negative", "positive_source", "attacked_positive"}
ALLOWED_SEED_ROLES = {"primary", "replicate"}


def _read_json(path: str | Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_non_empty_string(value: Any) -> bool:
    """判断值是否为非空字符串。"""
    return isinstance(value, str) and value.strip() != ""


def _is_non_bool_int(value: Any) -> bool:
    """判断值是否为整数, 排除 Python 中 bool 是 int 子类这一细节。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_number(value: Any) -> bool:
    """判断值是否为正数, 排除布尔值。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _is_placeholder_value(value: Any) -> bool:
    """判断 value pack 条目的 value 是否仍为占位内容。"""
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized == "" or any(marker in normalized for marker in PLACEHOLDER_MARKERS)
    return False


def _validate_value(replacement_key: str, value: Any) -> list[str]:
    """校验单个真实输入值的基本类型和取值范围。"""
    if replacement_key in {
        "prompt_text",
        "prompt_family",
        "license_note",
        "backend_type",
        "model_id",
        "scheduler",
        "watermark_method",
        "backend_command",
        "evidence_path",
    }:
        return [] if _is_non_empty_string(value) else ["must_be_non_empty_string"]
    if replacement_key == "split":
        return [] if value in ALLOWED_SPLITS else ["must_be_calibration_or_test"]
    if replacement_key == "sample_role":
        return [] if value in ALLOWED_SAMPLE_ROLES else ["must_be_supported_sample_role"]
    if replacement_key == "seed":
        return [] if _is_non_bool_int(value) and value >= 0 else ["must_be_non_negative_integer"]
    if replacement_key == "seed_role":
        return [] if value in ALLOWED_SEED_ROLES else ["must_be_primary_or_replicate"]
    if replacement_key == "num_inference_steps":
        return [] if _is_non_bool_int(value) and value > 0 else ["must_be_positive_integer"]
    if replacement_key == "guidance_scale":
        return [] if _is_positive_number(value) else ["must_be_positive_number"]
    if replacement_key == "image_size":
        valid = (
            isinstance(value, list)
            and len(value) == 2
            and all(_is_non_bool_int(item) and item > 0 for item in value)
        )
        return [] if valid else ["must_be_two_positive_integers"]
    if replacement_key == "requires_huggingface_token":
        return [] if isinstance(value, bool) else ["must_be_boolean"]
    if replacement_key == "payload_bits":
        if _is_non_empty_string(value):
            return []
        if isinstance(value, (list, dict)) and len(value) > 0:
            return []
        return ["must_be_non_empty_payload_spec"]
    if replacement_key == "watermark_strength":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return []
        if isinstance(value, dict) and len(value) > 0:
            return []
        return ["must_be_number_or_non_empty_object"]
    return []


def _entry_status(entry: dict[str, Any], validation_errors: list[str]) -> str:
    """返回单个 value pack 条目的填写和校验状态。"""
    if "value" not in entry:
        return "missing"
    if _is_placeholder_value(entry.get("value")):
        return "placeholder"
    if validation_errors:
        return "invalid"
    return "filled"


def _entry_row(entry: dict[str, Any]) -> dict[str, Any]:
    """构造单个 value pack 条目的状态行。"""
    replacement_key = str(entry.get("replacement_key", ""))
    value = entry.get("value")
    validation_errors = [] if "value" not in entry or _is_placeholder_value(value) else _validate_value(replacement_key, value)
    status = _entry_status(entry, validation_errors)
    return {
        "task_id": entry.get("task_id"),
        "relative_path": entry.get("relative_path"),
        "json_path": entry.get("json_path"),
        "placeholder_key": entry.get("placeholder_key"),
        "replacement_key": replacement_key,
        "status": status,
        "expected_content": entry.get("expected_content"),
        "value_placeholder": entry.get("value_placeholder"),
        "type_hint": TYPE_HINT_BY_REPLACEMENT_KEY.get(replacement_key, "真实实验配置值."),
        "validation_errors": validation_errors,
    }


def _blocking_item_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """把未通过的状态行转换为阻断项。"""
    return {
        "task_id": row["task_id"],
        "relative_path": row["relative_path"],
        "replacement_key": row["replacement_key"],
        "reason": row["status"],
        "type_hint": row["type_hint"],
        "expected_content": row["expected_content"],
        "validation_errors": row.get("validation_errors", []),
    }


def build_pilot_input_value_pack_status(
    *,
    workspace_root: str | Path,
    value_pack_path: str | Path | None = None,
) -> dict[str, Any]:
    """汇总真实 pilot 输入 value pack 的填写和校验进度。"""
    workspace = Path(workspace_root)
    pack_path = Path(value_pack_path) if value_pack_path is not None else workspace / VALUE_PACK_NAME
    if not pack_path.is_file():
        return {
            "artifact_name": STATUS_REPORT_NAME,
            "workspace_root": str(workspace),
            "value_pack_path": str(pack_path),
            "overall_decision": "fail",
            "recommended_next_stage": "create_pilot_input_value_pack",
            "value_entry_rows": [],
            "blocking_items": [
                {
                    "reason": "missing_value_pack",
                    "path": str(pack_path),
                    "action": "先运行 scaffold_pilot_input_value_pack.py 生成 value pack 草稿。",
                }
            ],
            "summary": {
                "value_entry_count": 0,
                "filled_count": 0,
                "missing_count": 0,
                "placeholder_count": 0,
                "invalid_count": 0,
                "blocking_item_count": 1,
            },
        }

    value_pack = _read_json(pack_path)
    rows = [_entry_row(entry) for entry in value_pack.get("value_entries", [])]
    blocking_rows = [row for row in rows if row["status"] != "filled"]
    blocking_items = [_blocking_item_from_row(row) for row in blocking_rows]
    decision = "pass" if not blocking_items else "fail"
    return {
        "artifact_name": STATUS_REPORT_NAME,
        "workspace_root": str(workspace),
        "value_pack_path": str(pack_path),
        "overall_decision": decision,
        "recommended_next_stage": (
            "apply_pilot_input_value_pack"
            if decision == "pass"
            else "fill_missing_real_values_in_value_pack"
        ),
        "value_entry_rows": rows,
        "blocking_items": blocking_items,
        "summary": {
            "value_entry_count": len(rows),
            "filled_count": sum(1 for row in rows if row["status"] == "filled"),
            "missing_count": sum(1 for row in rows if row["status"] == "missing"),
            "placeholder_count": sum(1 for row in rows if row["status"] == "placeholder"),
            "invalid_count": sum(1 for row in rows if row["status"] == "invalid"),
            "blocking_item_count": len(blocking_items),
        },
    }


def render_pilot_input_value_pack_status_markdown(report: dict[str, Any]) -> str:
    """把 value pack 填写状态渲染为 Markdown。"""
    lines = [
        "# pilot 输入 value pack 填写状态",
        "",
        f"- 工作区: `{report['workspace_root']}`",
        f"- value pack: `{report['value_pack_path']}`",
        f"- 总体结论: `{report['overall_decision']}`",
        f"- 推荐下一阶段: `{report['recommended_next_stage']}`",
        "",
        "## 汇总",
        "",
        "```text",
        f"value_entry_count = {report['summary']['value_entry_count']}",
        f"filled_count = {report['summary']['filled_count']}",
        f"missing_count = {report['summary']['missing_count']}",
        f"placeholder_count = {report['summary']['placeholder_count']}",
        f"invalid_count = {report['summary'].get('invalid_count', 0)}",
        f"blocking_item_count = {report['summary']['blocking_item_count']}",
        "```",
        "",
        "## 待处理条目",
        "",
    ]
    blocking_items = report.get("blocking_items", [])
    if not blocking_items:
        lines.append("当前 value pack 已填写完成且通过基本类型校验, 可以运行 apply_pilot_input_value_pack.py。")
    else:
        lines.append("| 顺序 | task_id | 目标字段 | 状态 | 类型提示 | 校验错误 |")
        lines.append("|---:|---|---|---|---|---|")
        for index, item in enumerate(blocking_items, start=1):
            errors = ", ".join(item.get("validation_errors", [])) or "-"
            lines.append(
                "| {index} | `{task_id}` | `{key}` | `{reason}` | {hint} | `{errors}` |".format(
                    index=index,
                    task_id=item.get("task_id", ""),
                    key=item.get("replacement_key", ""),
                    reason=item.get("reason", ""),
                    hint=item.get("type_hint", ""),
                    errors=errors,
                )
            )
    lines.extend(
        [
            "",
            "## 后续命令",
            "",
            "```text",
            "python scripts/build_pilot_input_value_pack_status.py --workspace <workspace> --require-pass",
            "python scripts/apply_pilot_input_value_pack.py --workspace <workspace> --value-pack <workspace>/pilot_input_value_pack.draft.json --require-pass",
            "python scripts/validate_pilot_input_plan_templates.py --workspace <workspace> --out <workspace>/pilot_input_plan_preflight_report.json --require-pass",
            "python scripts/build_pilot_execution_readiness_report.py --workspace <workspace> --out <workspace>/pilot_execution_readiness_report.json --require-pass",
            "python scripts/build_pilot_stage_progress_summary.py --workspace <workspace>",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_pilot_input_value_pack_status(
    *,
    workspace_root: str | Path,
    value_pack_path: str | Path | None,
    output_json_path: str | Path,
    output_markdown_path: str | Path,
) -> dict[str, Any]:
    """写出 value pack 填写状态 JSON 与 Markdown 报告。"""
    report = build_pilot_input_value_pack_status(workspace_root=workspace_root, value_pack_path=value_pack_path)
    _write_json(output_json_path, report)
    markdown_path = Path(output_markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_pilot_input_value_pack_status_markdown(report), encoding="utf-8")
    return report
