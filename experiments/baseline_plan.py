"""构建和执行外部 baseline 命令计划。

该模块把 Tree-Ring、Gaussian Shading、Shallow Diffuse、T2SMark 等第三方
实现作为外部命令处理。它只保存命令、输出路径和审计 manifest, 不把第三方算法复制进
CEG 核心方法层。
"""

from __future__ import annotations

import csv
import json
import shlex
from pathlib import Path
from typing import Any

from experiments.baseline_command_adapter import BaselineCommandSpec
from main.methods.baselines import get_baseline_spec


REQUIRED_PLAN_COLUMNS = ("baseline_id", "command", "output_path")


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON / JSONL baseline 命令计划。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("baseline plan JSON must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV baseline 命令计划。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _command_tuple(value: Any) -> tuple[str, ...]:
    """把命令字段转换为显式参数列表, 避免 shell 字符串拼接执行。"""
    if isinstance(value, list):
        command = tuple(str(part) for part in value)
    elif isinstance(value, str):
        command = tuple(shlex.split(value))
    else:
        raise TypeError("baseline command must be string or list")
    if not command:
        raise ValueError("baseline command must be non-empty")
    return command


def load_baseline_command_plan(path: str | Path) -> list[BaselineCommandSpec]:
    """从 JSON / JSONL / CSV 文件读取 baseline 命令计划。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported baseline plan file extension: {input_path.suffix}")
    specs: list[BaselineCommandSpec] = []
    for index, row in enumerate(rows):
        missing = [column for column in REQUIRED_PLAN_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"baseline plan row {index} missing columns: {missing}")
        baseline = get_baseline_spec(str(row["baseline_id"]))
        specs.append(
            BaselineCommandSpec(
                baseline_id=baseline.baseline_id,
                command=_command_tuple(row["command"]),
                output_path=str(row["output_path"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row.get("timeout_seconds", 3600)),
            )
        )
    return specs


def build_baseline_plan_manifest(specs: list[BaselineCommandSpec]) -> dict[str, Any]:
    """构造 baseline 命令计划 manifest, 用于记录正式实验外部依赖。"""
    return {
        "artifact_name": "baseline_command_plan_manifest.json",
        "baseline_count": len(specs),
        "baselines": [
            {
                "baseline_id": spec.baseline_id,
                "command": list(spec.command),
                "output_path": spec.output_path,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
            }
            for spec in specs
        ],
    }
