"""真实 pilot 输入值包模板与应用器。

该模块把替换清单进一步转成一个集中填写的值包。使用者先填写值包中的
`value` 字段, 再由应用器把这些值写回 prompt、split、seed、model 和
watermark 草稿计划。这样可以避免人工同时编辑多个 JSON 文件, 并让后续
preflight 有明确的输入来源。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


VALUE_PACK_NAME = "pilot_input_value_pack.draft.json"
VALUE_PACK_APPLICATION_REPORT_NAME = "pilot_input_value_pack_application_report.json"


VALUE_PLACEHOLDER_BY_REPLACEMENT_KEY = {
    "prompt_text": "replace_with_real_prompt_text",
    "prompt_family": "replace_with_prompt_family",
    "license_note": "replace_with_prompt_source_or_license_note",
    "split": "calibration_or_test",
    "sample_role": "clean_negative_or_positive_source",
    "seed": "replace_with_integer_seed",
    "seed_role": "primary_or_replicate",
    "backend_type": "diffusers_or_external_command",
    "model_id": "replace_with_sd_model_id_or_local_path",
    "scheduler": "replace_with_scheduler_name",
    "num_inference_steps": "replace_with_step_count",
    "guidance_scale": "replace_with_guidance_scale",
    "image_size": "replace_with_width_height_array",
    "requires_huggingface_token": "true_or_false",
    "watermark_method": "replace_with_ceg_watermark_method_or_external_method",
    "payload_bits": "replace_with_payload_bits_or_payload_spec",
    "watermark_strength": "replace_with_strength_or_embedding_params",
    "backend_command": "replace_with_command_or_internal_backend_id",
    "evidence_path": "replace_with_backend_log_or_run_manifest_path",
}


PLACEHOLDER_MARKERS = ("replace_with", "placeholder", "true_or_false", "calibration_or_test")


def _read_json(path: str | Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_pilot_input_value_pack_template(*, replacement_checklist_path: str | Path) -> dict[str, Any]:
    """基于替换清单生成集中填写的真实输入值包模板。"""
    checklist = _read_json(replacement_checklist_path)
    value_entries = []
    for task in checklist.get("replacement_tasks", []):
        replacement_key = task["replacement_key"]
        value_entries.append(
            {
                "task_id": task["task_id"],
                "relative_path": task["relative_path"],
                "json_path": task["json_path"],
                "placeholder_key": task["placeholder_key"],
                "replacement_key": replacement_key,
                "expected_content": task["expected_content"],
                "value_placeholder": VALUE_PLACEHOLDER_BY_REPLACEMENT_KEY.get(
                    replacement_key,
                    "replace_with_real_value",
                ),
            }
        )

    return {
        "artifact_name": VALUE_PACK_NAME,
        "source_replacement_checklist": str(replacement_checklist_path),
        "workspace_root": checklist.get("workspace_root"),
        "manifest_status": "draft_requires_real_values",
        "instructions": [
            "为每个 value_entries 项新增 value 字段.",
            "不要把 value_placeholder 改名为 value 后仍保留 replace_with 或 placeholder 文本.",
            "填写完成后运行 scripts/apply_pilot_input_value_pack.py.",
            "应用完成后重新运行 scripts/validate_pilot_input_plan_templates.py --require-pass.",
        ],
        "value_entries": value_entries,
        "summary": {
            "value_entry_count": len(value_entries),
            "source_blocking_item_count": checklist.get("summary", {}).get("blocking_item_count", 0),
        },
    }


def write_pilot_input_value_pack_template(
    *,
    replacement_checklist_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """写出真实输入值包模板。"""
    value_pack = build_pilot_input_value_pack_template(replacement_checklist_path=replacement_checklist_path)
    _write_json(output_path, value_pack)
    return value_pack


def _is_placeholder_value(value: Any) -> bool:
    """判断值包中的值是否仍是占位内容。"""
    if isinstance(value, str):
        normalized = value.strip().lower()
        return any(marker in normalized for marker in PLACEHOLDER_MARKERS)
    return False


def _parse_json_path(path: str) -> list[str | int]:
    """解析本项目 preflight 报告中使用的简单 JSON 路径。"""
    if not path.startswith("$."):
        raise ValueError(f"unsupported_json_path: {path}")
    tokens: list[str | int] = []
    for part in path[2:].split("."):
        match = re.fullmatch(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?", part)
        if not match:
            raise ValueError(f"unsupported_json_path_part: {part}")
        tokens.append(match.group(1))
        if match.group(2) is not None:
            tokens.append(int(match.group(2)))
    return tokens


def _replace_value_at_path(payload: Any, json_path: str, placeholder_key: str, replacement_key: str, value: Any) -> None:
    """在 JSON payload 中把占位字段替换为正式字段。"""
    tokens = _parse_json_path(json_path)
    if not tokens or tokens[-1] != placeholder_key:
        raise ValueError(f"json_path_does_not_end_with_placeholder_key: {json_path}")

    parent = payload
    for token in tokens[:-1]:
        parent = parent[token]
    if not isinstance(parent, dict):
        raise ValueError(f"json_path_parent_is_not_object: {json_path}")
    if placeholder_key not in parent:
        raise KeyError(f"missing_placeholder_key: {placeholder_key}")
    parent.pop(placeholder_key)
    parent[replacement_key] = value


def apply_pilot_input_value_pack(*, workspace_root: str | Path, value_pack_path: str | Path) -> dict[str, Any]:
    """把已填写的值包应用到真实 pilot 工作区草稿计划。"""
    workspace = Path(workspace_root)
    value_pack = _read_json(value_pack_path)
    grouped_payloads: dict[str, Any] = {}
    applied_tasks: list[dict[str, str]] = []
    blocking_items: list[dict[str, str]] = []

    for entry in value_pack.get("value_entries", []):
        task_id = entry["task_id"]
        relative_path = entry["relative_path"]
        value_present = "value" in entry
        value = entry.get("value")

        if not value_present or _is_placeholder_value(value):
            blocking_items.append(
                {
                    "task_id": task_id,
                    "relative_path": relative_path,
                    "reason": "missing_or_placeholder_value",
                }
            )
            continue

        if relative_path not in grouped_payloads:
            grouped_payloads[relative_path] = _read_json(workspace / relative_path)

        try:
            _replace_value_at_path(
                grouped_payloads[relative_path],
                entry["json_path"],
                entry["placeholder_key"],
                entry["replacement_key"],
                value,
            )
        except (KeyError, TypeError, ValueError) as exc:
            blocking_items.append(
                {
                    "task_id": task_id,
                    "relative_path": relative_path,
                    "reason": str(exc),
                }
            )
            continue

        applied_tasks.append(
            {
                "task_id": task_id,
                "relative_path": relative_path,
                "replacement_key": entry["replacement_key"],
            }
        )

    if blocking_items:
        decision = "fail"
    else:
        for relative_path, payload in grouped_payloads.items():
            _write_json(workspace / relative_path, payload)
        decision = "pass"

    return {
        "artifact_name": VALUE_PACK_APPLICATION_REPORT_NAME,
        "workspace_root": str(workspace),
        "value_pack_path": str(value_pack_path),
        "overall_decision": decision,
        "recommended_next_stage": (
            "rerun_pilot_input_plan_preflight"
            if decision == "pass"
            else "fill_missing_real_values_in_value_pack"
        ),
        "applied_tasks": applied_tasks,
        "blocking_items": blocking_items,
        "summary": {
            "value_entry_count": len(value_pack.get("value_entries", [])),
            "applied_task_count": len(applied_tasks),
            "blocking_item_count": len(blocking_items),
        },
    }


def apply_and_write_pilot_input_value_pack(
    *,
    workspace_root: str | Path,
    value_pack_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    """应用值包并写出应用报告。"""
    report = apply_pilot_input_value_pack(workspace_root=workspace_root, value_pack_path=value_pack_path)
    _write_json(report_path, report)
    return copy.deepcopy(report)
