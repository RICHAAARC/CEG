"""生成真实 pilot P0 输入用户交接包。

该模块把 P0 输入冻结阶段需要人工填写和复核的 CSV、指南、预检报告和状态报告
集中复制到一个交接目录。它不生成真实实验值, 不回写 value pack, 只把当前阻断证据
整理为用户可以直接打开和填写的文件集合。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from experiments.pilot_input_value_pack import VALUE_PACK_NAME
from experiments.pilot_input_value_pack_sheet import (
    FILL_SHEET_NAME,
    GUIDANCE_JSON_NAME,
    GUIDANCE_MARKDOWN_NAME,
    VALIDATION_MARKDOWN_NAME,
    VALIDATION_REPORT_NAME,
    export_pilot_input_value_pack_fill_sheet,
    export_pilot_input_value_pack_fill_sheet_guidance,
    validate_and_write_pilot_input_value_pack_fill_sheet,
)
from experiments.pilot_input_value_pack_status import STATUS_MARKDOWN_NAME, STATUS_REPORT_NAME

HANDOFF_ROOT_NAME = "user_handoff"
P0_HANDOFF_DIR_NAME = "p0_input_handoff"
P0_HANDOFF_MANIFEST_NAME = "p0_input_handoff_manifest.json"
P0_HANDOFF_README_NAME = "p0_input_handoff_readme.md"

OPTIONAL_SOURCE_NAMES = (
    STATUS_REPORT_NAME,
    STATUS_MARKDOWN_NAME,
    "pilot_stage_progress_summary.json",
    "pilot_stage_progress_summary.md",
    "pilot_p0_input_freeze_report.json",
    "pilot_p0_input_freeze_report.md",
)


def _read_json(path: str | Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, payload: Any) -> None:
    """写出 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_if_exists(source: Path, target_dir: Path) -> dict[str, Any]:
    """如果源文件存在, 则复制到交接目录并返回复制记录。"""
    record = {
        "source_path": str(source),
        "copied": False,
        "target_path": None,
    }
    if not source.is_file():
        record["missing"] = True
        return record
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    record.update({"copied": True, "missing": False, "target_path": str(target)})
    return record


def _render_readme(manifest: dict[str, Any]) -> str:
    """渲染 P0 用户交接包说明文档。"""
    validation = manifest.get("validation_summary", {})
    lines = [
        "# P0 输入冻结用户交接包",
        "",
        "该目录用于填写真实 pilot 输入。它不是论文结果包, 也不包含正式实验结果。",
        "",
        "## 当前结论",
        "",
        f"- 工作区: `{manifest.get('workspace_root')}`",
        f"- 总体预检结论: `{validation.get('overall_decision')}`",
        f"- 阻断项数量: `{validation.get('blocking_item_count')}`",
        f"- 是否回写 value pack: `{validation.get('write_performed')}`",
        "",
        "## 你需要编辑的文件",
        "",
        f"1. 打开 `{FILL_SHEET_NAME}`。",
        "2. 只填写 `value_json` 列。",
        "3. 不要修改 `task_id`、`relative_path`、`json_path`、`replacement_key` 或说明列。",
        "4. 字符串必须写成 JSON 字符串, 例如 `\"a realistic prompt\"`。",
        "5. 布尔值必须写成 `true` 或 `false`, 不能写成 `\"true\"` 或 `\"false\"`。",
        "6. 数组必须写成 JSON 数组, 例如 `[512, 512]`。",
        "",
        "## 填写后回到仓库运行",
        "",
        "```text",
        "python scripts/validate_pilot_input_value_pack_fill_sheet.py --workspace <workspace> --require-pass",
        "python scripts/import_pilot_input_value_pack_fill_sheet.py --workspace <workspace> --require-pass",
        "python scripts/build_pilot_p0_input_freeze_report.py --workspace <workspace> --dry-run --require-pass",
        "python scripts/build_pilot_p0_input_freeze_report.py --workspace <workspace> --require-pass",
        "```",
        "",
        "## 后续 GPU 暂停点",
        "",
        "P0 和 P1 通过后, 若图像生成启动计划通过且 `command_count > 0`, 本地应暂停, 由用户在真实 GPU / Colab / 外部 backend 环境执行图像生成和后续真实模型阶段。",
        "详细规则见 `docs/builds/paper_gpu_handoff_and_pause_plan.md`。",
        "",
        "## 本交接包内文件",
        "",
        "| 文件 | 状态 | 说明 |",
        "|---|---:|---|",
    ]
    descriptions = {
        FILL_SHEET_NAME: "需要人工填写 `value_json` 的 CSV。",
        GUIDANCE_MARKDOWN_NAME: "填写格式说明, 不提供真实实验值。",
        GUIDANCE_JSON_NAME: "机器可读填写指南。",
        VALIDATION_REPORT_NAME: "只读预检 JSON 报告。",
        VALIDATION_MARKDOWN_NAME: "只读预检 Markdown 报告。",
        P0_HANDOFF_MANIFEST_NAME: "本交接包 manifest。",
    }
    for item in manifest.get("copied_files", []):
        name = Path(str(item.get("target_path") or item.get("source_path", ""))).name
        status = "copied" if item.get("copied") else "missing"
        lines.append(f"| `{name}` | `{status}` | {descriptions.get(name, '辅助状态或阶段报告。')} |")
    lines.append("")
    return "\n".join(lines)


def build_pilot_p0_input_handoff_bundle(
    *,
    workspace_root: str | Path,
    output_root: str | Path | None = None,
    overwrite_fill_sheet: bool = False,
) -> dict[str, Any]:
    """构建 P0 输入冻结用户交接包。

    当填写表不存在或显式允许覆盖时, 函数会从 value pack 导出填写表。
    默认不覆盖已有填写表, 避免破坏用户已经填写的 `value_json`。
    预检报告始终基于当前填写表重新生成, 但不会回写 value pack。
    """
    workspace = Path(workspace_root)
    value_pack = workspace / VALUE_PACK_NAME
    fill_sheet = workspace / FILL_SHEET_NAME
    guidance_md = workspace / GUIDANCE_MARKDOWN_NAME
    guidance_json = workspace / GUIDANCE_JSON_NAME
    validation_json = workspace / VALIDATION_REPORT_NAME
    validation_md = workspace / VALIDATION_MARKDOWN_NAME
    handoff_root = Path(output_root) if output_root is not None else workspace / HANDOFF_ROOT_NAME / P0_HANDOFF_DIR_NAME

    created_or_refreshed = []
    if overwrite_fill_sheet or not fill_sheet.is_file():
        export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack, output_csv_path=fill_sheet)
        created_or_refreshed.append(str(fill_sheet))

    export_pilot_input_value_pack_fill_sheet_guidance(
        value_pack_path=value_pack,
        output_markdown_path=guidance_md,
        output_json_path=guidance_json,
    )
    created_or_refreshed.extend([str(guidance_md), str(guidance_json)])

    validation_report = validate_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack,
        input_csv_path=fill_sheet,
        report_path=validation_json,
        markdown_report_path=validation_md,
    )
    created_or_refreshed.extend([str(validation_json), str(validation_md)])

    source_names = [
        FILL_SHEET_NAME,
        GUIDANCE_MARKDOWN_NAME,
        GUIDANCE_JSON_NAME,
        VALIDATION_REPORT_NAME,
        VALIDATION_MARKDOWN_NAME,
        *OPTIONAL_SOURCE_NAMES,
    ]
    copied_files = [_copy_if_exists(workspace / name, handoff_root) for name in source_names]

    validation_summary = {
        "overall_decision": validation_report.get("overall_decision"),
        "recommended_next_stage": validation_report.get("recommended_next_stage"),
        "write_performed": validation_report.get("write_performed"),
        "blocking_item_count": validation_report.get("summary", {}).get("blocking_item_count"),
        "updated_entry_count": validation_report.get("summary", {}).get("updated_entry_count"),
    }
    manifest = {
        "artifact_name": P0_HANDOFF_MANIFEST_NAME,
        "workspace_root": str(workspace),
        "handoff_root": str(handoff_root),
        "value_pack_path": str(value_pack),
        "fill_sheet_path": str(fill_sheet),
        "overwrite_fill_sheet": overwrite_fill_sheet,
        "created_or_refreshed": created_or_refreshed,
        "copied_files": copied_files,
        "validation_summary": validation_summary,
        "overall_decision": validation_summary["overall_decision"],
        "recommended_next_stage": (
            "fill_value_json_and_rerun_p0_validation"
            if validation_summary["overall_decision"] != "pass"
            else "run_p0_input_freeze_dry_run"
        ),
        "gpu_pause_status": "not_reached_p0_still_blocking",
        "notes": [
            "本交接包只用于 P0 输入填写, 不包含论文正式实验结果。",
            "默认不覆盖已有 CSV 填写表, 避免破坏人工填写内容。",
            "预检报告不会回写 value pack。",
        ],
    }
    manifest_path = handoff_root / P0_HANDOFF_MANIFEST_NAME
    _write_json(manifest_path, manifest)
    readme_path = handoff_root / P0_HANDOFF_README_NAME
    readme_path.write_text(_render_readme(manifest), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    manifest["readme_path"] = str(readme_path)
    _write_json(manifest_path, manifest)
    return manifest
