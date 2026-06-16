"""导出和导入真实 pilot 输入 value pack 填写表。

该模块解决的问题是: 真实输入值目前分散在 JSON value pack 的多个条目中, 直接编辑 JSON
容易出错。这里提供 CSV 填写表, 让人工或外部系统只填写 `value_json` 列, 再由导入器
把值回写到 value pack。导入器只回写用户显式提供的 JSON 值, 不生成或猜测任何真实实验值。

通用工程写法是: 将结构化配置导出为可编辑表格, 再导入回原始配置。项目特定写法是:
保留 task_id、replacement_key、type_hint 和 expected_content, 并依赖 value pack status
报告执行后续类型和取值校验。
"""

from __future__ import annotations

import csv
import copy
import json
from pathlib import Path
from typing import Any

from experiments.pilot_input_value_pack import VALUE_PACK_NAME
from experiments.pilot_input_value_pack_status import TYPE_HINT_BY_REPLACEMENT_KEY, _entry_row


FILL_SHEET_NAME = "pilot_input_value_pack_fill_sheet.csv"
IMPORT_REPORT_NAME = "pilot_input_value_pack_fill_sheet_import_report.json"
GUIDANCE_MARKDOWN_NAME = "pilot_input_value_pack_fill_sheet_guidance.md"
GUIDANCE_JSON_NAME = "pilot_input_value_pack_fill_sheet_guidance.json"

CSV_COLUMNS = [
    "task_id",
    "relative_path",
    "json_path",
    "replacement_key",
    "type_hint",
    "expected_content",
    "value_json",
]

EXAMPLE_JSON_BY_REPLACEMENT_KEY = {
    "prompt_text": '"一段用于生成图像的真实 prompt 文本"',
    "prompt_family": '"object_scene"',
    "license_note": '"人工编写 prompt, 可用于本项目实验"',
    "split": '"calibration"',
    "sample_role": '"clean_negative"',
    "seed": "12345",
    "seed_role": '"primary"',
    "backend_type": '"external_command"',
    "model_id": '"runwayml/stable-diffusion-v1-5"',
    "scheduler": '"ddim"',
    "num_inference_steps": "50",
    "guidance_scale": "7.5",
    "image_size": "[512, 512]",
    "requires_huggingface_token": "false",
    "watermark_method": '"ceg"',
    "payload_bits": '"10101010"',
    "watermark_strength": "0.15",
    "backend_command": '"python path/to/backend.py --config path/to/config.json"',
    "evidence_path": '"runs/pilot/backend_execution_manifest.json"',
}


def _read_json(path: str | Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _value_to_json_cell(entry: dict[str, Any]) -> str:
    """把已有 value 转成 CSV 单元格中的 JSON 文本。"""
    if "value" not in entry:
        return ""
    return json.dumps(entry["value"], ensure_ascii=False)


def export_pilot_input_value_pack_fill_sheet(
    *,
    value_pack_path: str | Path,
    output_csv_path: str | Path,
) -> dict[str, Any]:
    """把 value pack 导出为可填写 CSV 表。"""
    value_pack = _read_json(value_pack_path)
    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in value_pack.get("value_entries", []):
        replacement_key = str(entry.get("replacement_key", ""))
        rows.append(
            {
                "task_id": entry.get("task_id", ""),
                "relative_path": entry.get("relative_path", ""),
                "json_path": entry.get("json_path", ""),
                "replacement_key": replacement_key,
                "type_hint": TYPE_HINT_BY_REPLACEMENT_KEY.get(replacement_key, "真实实验配置值."),
                "expected_content": entry.get("expected_content", ""),
                "value_json": _value_to_json_cell(entry),
            }
        )
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "artifact_name": FILL_SHEET_NAME,
        "value_pack_path": str(value_pack_path),
        "output_csv_path": str(output_path),
        "overall_decision": "pass",
        "row_count": len(rows),
        "instructions": [
            "只填写 value_json 列, 其他列用于定位和说明.",
            "字符串必须写成 JSON 字符串, 例如 \"a ceramic teapot\".",
            "布尔值必须写成 true 或 false, 不要写成 \"true\" 或 \"false\".",
            "数组必须写成 JSON 数组, 例如 [512, 512].",
            "填写后运行 import_pilot_input_value_pack_fill_sheet.py, 再运行 build_pilot_input_value_pack_status.py --require-pass.",
        ],
    }


def _guidance_row(entry: dict[str, Any]) -> dict[str, Any]:
    """构造单个 value_json 填写说明行, 只提供示例, 不生成真实实验值。"""
    replacement_key = str(entry.get("replacement_key", ""))
    return {
        "task_id": entry.get("task_id", ""),
        "replacement_key": replacement_key,
        "relative_path": entry.get("relative_path", ""),
        "json_path": entry.get("json_path", ""),
        "expected_content": entry.get("expected_content", ""),
        "type_hint": TYPE_HINT_BY_REPLACEMENT_KEY.get(replacement_key, "真实实验配置值."),
        "example_value_json": EXAMPLE_JSON_BY_REPLACEMENT_KEY.get(replacement_key, '"replace_with_real_value"'),
        "warning": "示例只说明 JSON 类型和格式, 不能直接作为正式论文实验输入.",
    }


def render_pilot_input_value_pack_fill_sheet_guidance_markdown(guidance: dict[str, Any]) -> str:
    """把 value_json 填写说明渲染为 Markdown。"""
    lines = [
        "# pilot 输入 value_json 填写指南",
        "",
        "本文档用于辅助填写 `pilot_input_value_pack_fill_sheet.csv` 的 `value_json` 列。",
        "它只给出 JSON 类型和格式示例, 不提供真实实验值, 也不能支撑任何论文结果声明。",
        "",
        "## 通用规则",
        "",
        "1. 只填写 CSV 中的 `value_json` 列, 不修改 `task_id` 和 `replacement_key`。",
        "2. 字符串必须写成 JSON 字符串, 例如 `\"a realistic prompt\"`。",
        "3. 布尔值必须写成 `true` 或 `false`, 不能写成 `\"true\"` 或 `\"false\"`。",
        "4. 数组必须写成 JSON 数组, 例如 `[512, 512]`。",
        "5. 对象必须写成 JSON 对象, 例如 `{\"strength\": 0.15}`。",
        "6. 填写完成后必须运行导入和状态校验命令, 不能手工认定通过。",
        "",
        "## 字段填写说明",
        "",
        "| 序号 | task_id | replacement_key | value_json 示例 | 类型要求 |",
        "|---:|---|---|---|---|",
    ]
    for index, row in enumerate(guidance.get("guidance_rows", []), start=1):
        lines.append(
            "| {index} | `{task_id}` | `{key}` | `{example}` | {hint} |".format(
                index=index,
                task_id=row.get("task_id", ""),
                key=row.get("replacement_key", ""),
                example=row.get("example_value_json", ""),
                hint=row.get("type_hint", ""),
            )
        )
    lines.extend(
        [
            "",
            "## 填写后验证命令",
            "",
            "```text",
            "python scripts/import_pilot_input_value_pack_fill_sheet.py --workspace <workspace> --require-pass",
            "python scripts/build_pilot_input_value_pack_status.py --workspace <workspace> --require-pass",
            "python scripts/apply_pilot_input_value_pack.py --workspace <workspace> --value-pack <workspace>/pilot_input_value_pack.draft.json --require-pass",
            "python scripts/validate_pilot_input_plan_templates.py --workspace <workspace> --out <workspace>/pilot_input_plan_preflight_report.json --require-pass",
            "python scripts/build_pilot_execution_readiness_report.py --workspace <workspace> --out <workspace>/pilot_execution_readiness_report.json --require-pass",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def export_pilot_input_value_pack_fill_sheet_guidance(
    *,
    value_pack_path: str | Path,
    output_markdown_path: str | Path,
    output_json_path: str | Path,
) -> dict[str, Any]:
    """导出 value_json 填写指南, 只辅助人工填写, 不写入 value pack。"""
    value_pack = _read_json(value_pack_path)
    guidance = {
        "artifact_name": GUIDANCE_JSON_NAME,
        "value_pack_path": str(value_pack_path),
        "output_markdown_path": str(output_markdown_path),
        "output_json_path": str(output_json_path),
        "overall_decision": "pass",
        "guidance_only": True,
        "warning": "本文件只说明 value_json 格式, 不包含真实实验值, 不能作为论文结果证据.",
        "guidance_rows": [_guidance_row(entry) for entry in value_pack.get("value_entries", [])],
        "summary": {
            "guidance_row_count": len(value_pack.get("value_entries", [])),
        },
    }
    _write_json(output_json_path, guidance)
    markdown_path = Path(output_markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_pilot_input_value_pack_fill_sheet_guidance_markdown(guidance),
        encoding="utf-8",
    )
    return guidance


def _read_sheet_rows(csv_path: str | Path) -> list[dict[str, str]]:
    """读取 CSV 填写表。"""
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _parse_value_json(raw: str) -> tuple[Any | None, str | None]:
    """解析 value_json 单元格。空单元格表示该条目未填写。"""
    text = raw.strip()
    if text == "":
        return None, "empty_value_json"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"


def _status_blocking_item_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """对模拟回写后的 value entry 执行状态校验, 返回阻断项。"""
    row = _entry_row(entry)
    if row["status"] == "filled":
        return None
    return {
        "task_id": row["task_id"],
        "replacement_key": row["replacement_key"],
        "reason": row["status"],
        "validation_errors": row.get("validation_errors", []),
    }


def import_pilot_input_value_pack_fill_sheet(
    *,
    value_pack_path: str | Path,
    input_csv_path: str | Path,
    output_value_pack_path: str | Path | None = None,
) -> dict[str, Any]:
    """把 CSV 填写表中的 value_json 安全回写到 value pack。

    导入器会先在内存中模拟回写, 再复用 value pack status 的类型和取值校验。
    只有全部条目都解析成功且校验通过时, 才会写入目标 value pack。
    """
    value_pack = _read_json(value_pack_path)
    candidate_value_pack = copy.deepcopy(value_pack)
    rows = _read_sheet_rows(input_csv_path)
    row_by_task_id = {row.get("task_id", ""): row for row in rows}
    candidate_updated_entries = []
    blocking_items = []

    for entry in candidate_value_pack.get("value_entries", []):
        task_id = str(entry.get("task_id", ""))
        row = row_by_task_id.get(task_id)
        if row is None:
            blocking_items.append({"task_id": task_id, "reason": "missing_sheet_row"})
            continue
        value, error = _parse_value_json(row.get("value_json", ""))
        if error is not None:
            blocking_items.append({"task_id": task_id, "reason": error})
            continue
        entry["value"] = value
        if status_blocking := _status_blocking_item_from_entry(entry):
            blocking_items.append(status_blocking)
            continue
        candidate_updated_entries.append({"task_id": task_id, "replacement_key": entry.get("replacement_key")})

    decision = "pass" if not blocking_items else "fail"
    target_path = Path(output_value_pack_path) if output_value_pack_path is not None else Path(value_pack_path)
    updated_entries = candidate_updated_entries if decision == "pass" else []
    if decision == "pass":
        _write_json(target_path, candidate_value_pack)
    return {
        "artifact_name": IMPORT_REPORT_NAME,
        "value_pack_path": str(value_pack_path),
        "input_csv_path": str(input_csv_path),
        "output_value_pack_path": str(target_path),
        "overall_decision": decision,
        "recommended_next_stage": (
            "run_value_pack_status_validation" if decision == "pass" else "fix_value_pack_fill_sheet"
        ),
        "updated_entries": updated_entries,
        "blocking_items": blocking_items,
        "summary": {
            "sheet_row_count": len(rows),
            "value_entry_count": len(value_pack.get("value_entries", [])),
            "updated_entry_count": len(updated_entries),
            "blocking_item_count": len(blocking_items),
        },
    }


def import_and_write_pilot_input_value_pack_fill_sheet(
    *,
    value_pack_path: str | Path,
    input_csv_path: str | Path,
    output_value_pack_path: str | Path | None,
    report_path: str | Path,
) -> dict[str, Any]:
    """导入 CSV 填写表并写出导入报告。"""
    report = import_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack_path,
        input_csv_path=input_csv_path,
        output_value_pack_path=output_value_pack_path,
    )
    _write_json(report_path, report)
    return report
