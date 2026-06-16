"""执行外部 CEG detector 命令计划并校验 detection 输出契约。

该模块用于把真实 CEG detector backend 接入论文流程。它只负责调度外部命令、读取
`detection_events.json` 与 `detection_thresholds.json`, 并写出执行 manifest。真实模型、
权重加载、水印检测和几何恢复算法不放入这里, 以保持 `main/methods/ceg` 核心方法层干净。
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

from main.core.digest import build_stable_digest

REQUIRED_DETECTION_PLAN_COLUMNS = ("detector_id", "command", "output_root")
DETECTION_EVENTS_NAME = "detection_events.json"
DETECTION_THRESHOLDS_NAME = "detection_thresholds.json"
DETECTION_EXECUTION_MANIFEST_NAME = "ceg_detection_execution_manifest.json"
REQUIRED_DETECTION_OUTPUTS = (DETECTION_EVENTS_NAME, DETECTION_THRESHOLDS_NAME)


@dataclass(frozen=True)
class DetectionCommandSpec:
    """表示一个外部 CEG detector backend 的最小命令契约。"""

    detector_id: str
    command: tuple[str, ...]
    output_root: str
    working_directory: str | None = None
    timeout_seconds: int = 3600

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 manifest 的普通字典。"""
        payload = asdict(self)
        payload["command"] = list(self.command)
        return payload


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSON / JSONL detector 命令计划。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("detection plan JSON must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV detector 命令计划。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _command_tuple(value: Any) -> tuple[str, ...]:
    """把命令字段转换为显式 argv, 避免 shell 字符串拼接。"""
    if isinstance(value, list):
        command = tuple(str(part) for part in value)
    elif isinstance(value, str):
        command = tuple(shlex.split(value))
    else:
        raise TypeError("detection command must be string or list")
    if not command:
        raise ValueError("detection command must be non-empty")
    return command


def load_detection_command_plan(path: str | Path) -> list[DetectionCommandSpec]:
    """从 JSON / JSONL / CSV 文件读取外部 detector 命令计划。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported detection plan file extension: {input_path.suffix}")
    specs: list[DetectionCommandSpec] = []
    for index, row in enumerate(rows):
        missing = [column for column in REQUIRED_DETECTION_PLAN_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"detection plan row {index} missing columns: {missing}")
        specs.append(
            DetectionCommandSpec(
                detector_id=str(row["detector_id"]),
                command=_command_tuple(row["command"]),
                output_root=str(row["output_root"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row.get("timeout_seconds", 3600)),
            )
        )
    return specs


def build_detection_plan_manifest(specs: list[DetectionCommandSpec]) -> dict[str, Any]:
    """构建外部 detector 命令计划 manifest。"""
    records = [spec.to_dict() for spec in specs]
    return {
        "artifact_name": "ceg_detection_command_plan_manifest.json",
        "detector_count": len(specs),
        "required_detection_outputs": list(REQUIRED_DETECTION_OUTPUTS),
        "detectors": records,
        "plan_digest": build_stable_digest(records),
    }


def validate_detection_output_root(output_root: str | Path) -> dict[str, Any]:
    """校验外部 detector 是否产出 CEG 阶段 4 必需文件。"""
    root = Path(output_root)
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative in REQUIRED_DETECTION_OUTPUTS:
        candidate = root / relative
        exists = candidate.is_file()
        if not exists:
            missing.append(relative)
        checks.append(
            {
                "relative_path": relative,
                "path": str(candidate),
                "exists": exists,
                "byte_count": candidate.stat().st_size if exists else 0,
            }
        )
    event_count = 0
    threshold_count = 0
    if not missing:
        events = json.loads((root / DETECTION_EVENTS_NAME).read_text(encoding="utf-8-sig"))
        thresholds = json.loads((root / DETECTION_THRESHOLDS_NAME).read_text(encoding="utf-8-sig"))
        if not isinstance(events, list):
            raise TypeError("detection_events.json must contain a list")
        if not isinstance(thresholds, dict):
            raise TypeError("detection_thresholds.json must contain an object")
        event_count = len(events)
        threshold_count = len(thresholds)
    return {
        "output_root": str(root),
        "overall_decision": "pass" if not missing else "fail",
        "missing_required_outputs": missing,
        "event_count": event_count,
        "threshold_count": threshold_count,
        "checks": checks,
    }


def run_detection_command_plan(specs: list[DetectionCommandSpec]) -> dict[str, Any]:
    """执行外部 detector 命令计划并收集输出契约校验结果。"""
    results: list[dict[str, Any]] = []
    for spec in specs:
        completed = subprocess.run(
            list(spec.command),
            cwd=spec.working_directory or None,
            check=False,
            text=True,
            capture_output=True,
            timeout=spec.timeout_seconds,
        )
        output_contract = (
            validate_detection_output_root(spec.output_root)
            if completed.returncode == 0
            else {
                "output_root": spec.output_root,
                "overall_decision": "fail",
                "missing_required_outputs": list(REQUIRED_DETECTION_OUTPUTS),
                "event_count": 0,
                "threshold_count": 0,
                "checks": [],
            }
        )
        results.append(
            {
                "detector_id": spec.detector_id,
                "command": list(spec.command),
                "output_root": spec.output_root,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
                "return_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "output_contract": output_contract,
            }
        )
    pass_count = sum(
        1 for item in results if item["return_code"] == 0 and item["output_contract"]["overall_decision"] == "pass"
    )
    return {
        "artifact_name": "ceg_detection_command_results.json",
        "detector_count": len(specs),
        "pass_count": pass_count,
        "results": results,
    }
