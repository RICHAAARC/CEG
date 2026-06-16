"""真实 pilot 输入计划预检门禁。

该模块的作用是检查真实 pilot 工作区中的 prompt、split、seed、model 和
watermark 配置是否仍包含占位字段。它只读取 JSON 计划文件并生成结构化报告,
不运行 SD、watermark、attack 或 detector, 因此适合在昂贵实验启动前作为
轻量门禁复用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PREFLIGHT_REPORT_NAME = "pilot_input_plan_preflight_report.json"


REQUIRED_PLAN_FILES = {
    "prompt_plan": Path("inputs/prompts/prompt_plan.draft.json"),
    "split_plan": Path("inputs/prompts/split_plan.draft.json"),
    "seed_plan": Path("inputs/prompts/seed_plan.draft.json"),
    "model_config": Path("configs/model_config.draft.json"),
    "watermark_config": Path("configs/watermark_config.draft.json"),
}


PLACEHOLDER_VALUE_MARKERS = (
    "replace_with",
    "placeholder",
    "calibration_or_test",
    "positive_source_or_clean_negative",
    "true_or_false",
)


@dataclass(frozen=True)
class PlaceholderFinding:
    """描述一个仍需替换的占位项。"""

    file_key: str
    relative_path: str
    json_path: str
    finding_type: str
    evidence: str

    def to_record(self) -> dict[str, str]:
        """转换为可写入 JSON 报告的记录结构。"""
        return {
            "file_key": self.file_key,
            "relative_path": self.relative_path,
            "json_path": self.json_path,
            "finding_type": self.finding_type,
            "evidence": self.evidence,
        }


def _load_json(path: Path) -> Any:
    """按 UTF-8 读取 JSON 文件, 让 Windows 与 Colab 运行结果保持一致。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _json_path(parent: str, key: str | int) -> str:
    """构造报告中使用的 JSON 路径。"""
    if isinstance(key, int):
        return f"{parent}[{key}]"
    if parent == "$":
        return f"$.{key}"
    return f"{parent}.{key}"


def _is_placeholder_value(value: str) -> bool:
    """判断字符串值是否仍像占位提示而不是真实实验配置。"""
    normalized = value.strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_VALUE_MARKERS)


def _scan_placeholders(
    *,
    file_key: str,
    relative_path: Path,
    node: Any,
    json_path: str = "$",
) -> list[PlaceholderFinding]:
    """递归扫描 JSON 节点中的占位字段名和占位字段值。"""
    findings: list[PlaceholderFinding] = []
    relative = relative_path.as_posix()

    if isinstance(node, dict):
        for key, value in node.items():
            current_path = _json_path(json_path, key)
            if key.endswith("_placeholder"):
                findings.append(
                    PlaceholderFinding(
                        file_key=file_key,
                        relative_path=relative,
                        json_path=current_path,
                        finding_type="placeholder_key",
                        evidence=key,
                    )
                )
            findings.extend(
                _scan_placeholders(
                    file_key=file_key,
                    relative_path=relative_path,
                    node=value,
                    json_path=current_path,
                )
            )
    elif isinstance(node, list):
        for index, value in enumerate(node):
            findings.extend(
                _scan_placeholders(
                    file_key=file_key,
                    relative_path=relative_path,
                    node=value,
                    json_path=_json_path(json_path, index),
                )
            )
    elif isinstance(node, str) and _is_placeholder_value(node):
        findings.append(
            PlaceholderFinding(
                file_key=file_key,
                relative_path=relative,
                json_path=json_path,
                finding_type="placeholder_value",
                evidence=node,
            )
        )

    return findings


def build_pilot_input_plan_preflight_report(*, workspace_root: str | Path) -> dict[str, Any]:
    """生成真实 pilot 输入计划预检报告。"""
    root = Path(workspace_root)
    missing_files: list[dict[str, str]] = []
    unreadable_files: list[dict[str, str]] = []
    scanned_files: list[dict[str, str]] = []
    findings: list[PlaceholderFinding] = []

    for file_key, relative_path in REQUIRED_PLAN_FILES.items():
        absolute_path = root / relative_path
        if not absolute_path.is_file():
            missing_files.append({"file_key": file_key, "relative_path": relative_path.as_posix()})
            continue

        try:
            payload = _load_json(absolute_path)
        except json.JSONDecodeError as exc:
            unreadable_files.append(
                {
                    "file_key": file_key,
                    "relative_path": relative_path.as_posix(),
                    "error": f"json_decode_error: {exc}",
                }
            )
            continue

        scanned_files.append({"file_key": file_key, "relative_path": relative_path.as_posix()})
        findings.extend(_scan_placeholders(file_key=file_key, relative_path=relative_path, node=payload))

    fail_count = len(missing_files) + len(unreadable_files) + len(findings)
    overall_decision = "pass" if fail_count == 0 else "fail"

    return {
        "artifact_name": PREFLIGHT_REPORT_NAME,
        "workspace_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": (
            "real_image_generation_pilot"
            if overall_decision == "pass"
            else "replace_pilot_input_plan_placeholders"
        ),
        "scanned_files": scanned_files,
        "missing_files": missing_files,
        "unreadable_files": unreadable_files,
        "placeholder_findings": [finding.to_record() for finding in findings],
        "summary": {
            "required_file_count": len(REQUIRED_PLAN_FILES),
            "scanned_file_count": len(scanned_files),
            "missing_file_count": len(missing_files),
            "unreadable_file_count": len(unreadable_files),
            "placeholder_finding_count": len(findings),
            "blocking_item_count": fail_count,
        },
    }


def write_pilot_input_plan_preflight_report(
    *,
    workspace_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """写出真实 pilot 输入计划预检报告。"""
    report = build_pilot_input_plan_preflight_report(workspace_root=workspace_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
