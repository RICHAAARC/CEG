"""执行外部高级指标命令计划。

外部高级指标包括 LPIPS、FID 和 CLIP score 等依赖深度学习框架或第三方模型的指标。
该模块只负责任务调度和结果收集, 不把重型依赖引入默认 pytest 路径。
"""

from __future__ import annotations

import csv
import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from experiments.metric_file_adapter import load_metric_rows


REQUIRED_METRIC_PLAN_COLUMNS = ("metric_name", "command", "output_path")


@dataclass(frozen=True)
class MetricCommandSpec:
    """表示一个外部高级指标命令。"""

    metric_name: str
    command: tuple[str, ...]
    output_path: str
    working_directory: str | None = None
    timeout_seconds: int = 3600

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典, 便于 manifest 保存。"""
        payload = asdict(self)
        payload["command"] = list(self.command)
        return payload


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON / JSONL metric 命令计划。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("metric plan JSON must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV metric 命令计划。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _command_tuple(value: Any) -> tuple[str, ...]:
    """把命令字段转换为显式参数列表。"""
    if isinstance(value, list):
        command = tuple(str(part) for part in value)
    elif isinstance(value, str):
        command = tuple(shlex.split(value))
    else:
        raise TypeError("metric command must be string or list")
    if not command:
        raise ValueError("metric command must be non-empty")
    return command


def load_metric_command_plan(path: str | Path) -> list[MetricCommandSpec]:
    """从 JSON / JSONL / CSV 文件读取外部高级指标命令计划。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported metric plan file extension: {input_path.suffix}")
    specs: list[MetricCommandSpec] = []
    for index, row in enumerate(rows):
        missing = [column for column in REQUIRED_METRIC_PLAN_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"metric plan row {index} missing columns: {missing}")
        specs.append(
            MetricCommandSpec(
                metric_name=str(row["metric_name"]),
                command=_command_tuple(row["command"]),
                output_path=str(row["output_path"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row.get("timeout_seconds", 3600)),
            )
        )
    return specs


def build_metric_plan_manifest(specs: list[MetricCommandSpec]) -> dict[str, Any]:
    """构建外部高级指标命令计划 manifest。"""
    return {
        "artifact_name": "metric_command_plan_manifest.json",
        "metric_command_count": len(specs),
        "metrics": [spec.to_dict() for spec in specs],
    }


def run_metric_command_plan(specs: list[MetricCommandSpec]) -> dict[str, Any]:
    """执行高级指标命令并收集返回码。"""
    results: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    for spec in specs:
        completed = subprocess.run(
            list(spec.command),
            cwd=spec.working_directory or None,
            check=False,
            text=True,
            capture_output=True,
            timeout=spec.timeout_seconds,
        )
        output_path = Path(spec.output_path)
        if completed.returncode == 0 and output_path.exists():
            metric_rows.extend(load_metric_rows(output_path))
        results.append(
            {
                "metric_name": spec.metric_name,
                "command": list(spec.command),
                "output_path": spec.output_path,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
                "return_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "metric_row_count": len(metric_rows),
            }
        )
    return {"results": results, "metric_rows": metric_rows}
