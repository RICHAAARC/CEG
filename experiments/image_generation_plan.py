"""执行外部图像生成命令计划并校验输出契约。

该模块用于把真实 SD / watermark backend 接入 CEG 论文流程。它只调度外部命令并检查
外部命令是否产出 prompt plan、image pairs 和 image manifests, 不把 SD 或水印算法本体复制到
CEG 核心方法层。这样做属于通用工程写法: 外部重型依赖通过显式 argv、输出路径和 manifest
进入受治理结果包。项目特定部分在于输出契约固定为 CEG 论文阶段 2 所需的图像 provenance 文件。
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

REQUIRED_IMAGE_GENERATION_PLAN_COLUMNS = ("backend_id", "command", "output_root")
REQUIRED_EXTERNAL_OUTPUTS = (
    "prompt_plan.json",
    "image_pairs.json",
    "image_manifests/image_generation_manifest.json",
    "image_manifests/image_pair_manifest.json",
)


@dataclass(frozen=True)
class ImageGenerationCommandSpec:
    """表示一个外部图像生成 backend 的最小命令契约。"""

    backend_id: str
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
    """读取 JSON / JSONL 图像生成命令计划。"""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise TypeError("image generation plan JSON must contain a list")
    return [dict(row) for row in payload]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """读取 CSV 图像生成命令计划。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _command_tuple(value: Any) -> tuple[str, ...]:
    """把命令字段转换为显式 argv, 避免 shell 字符串拼接。"""
    if isinstance(value, list):
        command = tuple(str(part) for part in value)
    elif isinstance(value, str):
        command = tuple(shlex.split(value))
    else:
        raise TypeError("image generation command must be string or list")
    if not command:
        raise ValueError("image generation command must be non-empty")
    return command


def load_image_generation_command_plan(path: str | Path) -> list[ImageGenerationCommandSpec]:
    """从 JSON / JSONL / CSV 文件读取外部图像生成命令计划。"""
    input_path = Path(path)
    if input_path.suffix in {".json", ".jsonl"}:
        rows = _load_json_or_jsonl(input_path)
    elif input_path.suffix == ".csv":
        rows = _load_csv(input_path)
    else:
        raise ValueError(f"unsupported image generation plan file extension: {input_path.suffix}")
    specs: list[ImageGenerationCommandSpec] = []
    for index, row in enumerate(rows):
        missing = [column for column in REQUIRED_IMAGE_GENERATION_PLAN_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"image generation plan row {index} missing columns: {missing}")
        specs.append(
            ImageGenerationCommandSpec(
                backend_id=str(row["backend_id"]),
                command=_command_tuple(row["command"]),
                output_root=str(row["output_root"]),
                working_directory=str(row["working_directory"]) if row.get("working_directory") else None,
                timeout_seconds=int(row.get("timeout_seconds", 3600)),
            )
        )
    return specs


def build_image_generation_plan_manifest(specs: list[ImageGenerationCommandSpec]) -> dict[str, Any]:
    """构建外部图像生成命令计划 manifest。"""
    records = [spec.to_dict() for spec in specs]
    return {
        "artifact_name": "image_generation_command_plan_manifest.json",
        "image_generation_backend_count": len(specs),
        "required_external_outputs": list(REQUIRED_EXTERNAL_OUTPUTS),
        "backends": records,
        "plan_digest": build_stable_digest(records),
    }


def validate_image_generation_output_root(output_root: str | Path) -> dict[str, Any]:
    """校验外部图像生成 backend 是否产出 CEG 阶段 2 必需文件。"""
    root = Path(output_root)
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative in REQUIRED_EXTERNAL_OUTPUTS:
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
    return {
        "output_root": str(root),
        "overall_decision": "pass" if not missing else "fail",
        "missing_required_outputs": missing,
        "checks": checks,
    }


def run_image_generation_command_plan(specs: list[ImageGenerationCommandSpec]) -> dict[str, Any]:
    """执行外部图像生成命令计划并收集输出契约校验结果。"""
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
        output_contract = validate_image_generation_output_root(spec.output_root) if completed.returncode == 0 else {
            "output_root": spec.output_root,
            "overall_decision": "fail",
            "missing_required_outputs": list(REQUIRED_EXTERNAL_OUTPUTS),
            "checks": [],
        }
        results.append(
            {
                "backend_id": spec.backend_id,
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
    return {
        "artifact_name": "image_generation_command_results.json",
        "backend_count": len(specs),
        "pass_count": sum(1 for item in results if item["return_code"] == 0 and item["output_contract"]["overall_decision"] == "pass"),
        "results": results,
    }
