"""物化外部 baseline 和高级指标命令模板。

该模块解决的问题是: 配置中通常只想写一次第三方项目的命令模板, 但正式运行时需要展开为显式 argv 列表。
显式 argv 列表比 shell 字符串更安全, 也更容易写入 manifest 做复现审计。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.baseline_command_adapter import BaselineCommandSpec
from experiments.image_generation_plan import ImageGenerationCommandSpec
from main.methods.baselines import get_baseline_spec


@dataclass(frozen=True)
class CommandTemplateSpec:
    """表示一个可物化为命令计划的模板。"""

    template_id: str
    command_template: tuple[str, ...]
    output_path_template: str
    working_directory_template: str | None
    timeout_seconds: int
    template_role: str


def _load_template_rows(path: Path) -> list[dict[str, Any]]:
    """读取 JSON 模板文件。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        rows = payload.get("templates", [])
    else:
        rows = payload
    if not isinstance(rows, list):
        raise TypeError("command template file must contain a list or a templates list")
    return [dict(row) for row in rows]


def load_command_templates(path: str | Path, *, template_role: str) -> list[CommandTemplateSpec]:
    """读取命令模板并归一化字段。"""
    specs: list[CommandTemplateSpec] = []
    for index, row in enumerate(_load_template_rows(Path(path))):
        template_id = str(row.get("baseline_id") or row.get("metric_name") or row.get("backend_id") or row.get("template_id") or "").strip()
        if not template_id:
            raise ValueError(f"command template row {index} missing template id")
        command_template = row.get("command_template")
        if not isinstance(command_template, list) or not command_template:
            raise ValueError(f"command template row {index} must contain non-empty command_template list")
        specs.append(
            CommandTemplateSpec(
                template_id=template_id,
                command_template=tuple(str(part) for part in command_template),
                output_path_template=str(row.get("output_path_template") or "{output_root}/{template_id}.json"),
                working_directory_template=(
                    str(row["working_directory_template"]) if row.get("working_directory_template") else None
                ),
                timeout_seconds=int(row.get("timeout_seconds", 3600)),
                template_role=template_role,
            )
        )
    return specs


def _format_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    """把格式化变量统一转换为字符串。"""
    return {key: str(value) for key, value in mapping.items()}


def materialize_command_template(spec: CommandTemplateSpec, variables: dict[str, Any]) -> dict[str, Any]:
    """把模板物化为通用命令计划行。"""
    mapping = _format_mapping({"template_id": spec.template_id, **variables})
    command = [part.format_map(mapping) for part in spec.command_template]
    output_path = spec.output_path_template.format_map(mapping)
    working_directory = (
        spec.working_directory_template.format_map(mapping) if spec.working_directory_template else None
    )
    return {
        "template_id": spec.template_id,
        "command": command,
        "output_path": output_path,
        "working_directory": working_directory,
        "timeout_seconds": spec.timeout_seconds,
        "template_role": spec.template_role,
    }


def materialize_baseline_command_plan(template_path: str | Path, variables: dict[str, Any]) -> list[BaselineCommandSpec]:
    """把 baseline 命令模板物化为现有 baseline runner 可消费的计划。"""
    rows: list[BaselineCommandSpec] = []
    for spec in load_command_templates(template_path, template_role="external_baseline"):
        baseline = get_baseline_spec(spec.template_id)
        row = materialize_command_template(spec, {"baseline_id": baseline.baseline_id, **variables})
        rows.append(
            BaselineCommandSpec(
                baseline_id=baseline.baseline_id,
                command=tuple(row["command"]),
                output_path=str(row["output_path"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row["timeout_seconds"]),
            )
        )
    return rows


def materialize_metric_command_plan(template_path: str | Path, variables: dict[str, Any]) -> list[dict[str, Any]]:
    """把高级指标命令模板物化为 metric runner 可消费的通用计划行。"""
    rows: list[dict[str, Any]] = []
    for spec in load_command_templates(template_path, template_role="external_metric"):
        row = materialize_command_template(spec, {"metric_name": spec.template_id, **variables})
        row["metric_name"] = spec.template_id
        rows.append(row)
    return rows


def materialize_image_generation_command_plan(template_path: str | Path, variables: dict[str, Any]) -> list[ImageGenerationCommandSpec]:
    """把图像生成命令模板物化为外部 image generation runner 可消费的计划。"""
    rows: list[ImageGenerationCommandSpec] = []
    for spec in load_command_templates(template_path, template_role="external_image_generation"):
        row = materialize_command_template(spec, {"backend_id": spec.template_id, **variables})
        rows.append(
            ImageGenerationCommandSpec(
                backend_id=spec.template_id,
                command=tuple(row["command"]),
                output_root=str(row["output_path"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row["timeout_seconds"]),
            )
        )
    return rows
