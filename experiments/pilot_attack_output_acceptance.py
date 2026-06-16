"""校验 attack pilot 输出是否可进入 detection 与 fixed-FPR 统计。

该模块位于 experiments 层, 用于接收 `run_image_attack_workflow.py` 或外部 attack backend 已经写出的
attack 结果。它只检查 attacked image、attack manifest 和 attacked image pairs 的文件契约,
不运行攻击算法, 不运行检测器, 也不把 dry-run attack 声明为正式论文结果。

通用工程写法是: 对独立阶段的输出建立接收门禁, 防止坏路径或缺失 provenance 被带入后续统计。
项目特定写法是: 固定检查 CEG 论文流程约定的 attacked_image_manifest、attack_shard_manifest 和
image_pairs_attacked, 并给出是否可以进入 CEG detector pilot 的机器可读结论。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

REPORT_NAME = "pilot_attack_output_acceptance_report.json"
NEXT_STAGE_ON_PASS = "ceg_detection_pilot"
NEXT_STAGE_ON_FAIL = "run_attack_backend_and_fix_outputs"
REQUIRED_ATTACK_OUTPUTS = (
    "image_pairs_attacked.json",
    "image_manifests/attacked_image_manifest.json",
    "image_manifests/attack_shard_manifest.json",
)
REQUIRED_ATTACK_RECORD_FIELDS = (
    "attacked_image_path",
    "watermarked_image_path",
    "attack_family",
    "attack_condition",
)


@dataclass(frozen=True)
class PathCheck:
    """表示一个 attack 输出路径检查。"""

    field_name: str
    value: str
    resolved_path: Path
    exists: bool
    byte_count: int

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 JSON 报告的普通字典。"""
        return {
            "field_name": self.field_name,
            "value": self.value,
            "resolved_path": str(self.resolved_path),
            "exists": self.exists,
            "byte_count": self.byte_count,
        }


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(output_root: Path, value: str) -> Path:
    """把相对路径解析到 attack 输出根目录下。"""
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return output_root / candidate


def _path_check(output_root: Path, row: dict[str, Any], field_name: str) -> PathCheck | None:
    """检查单个路径字段是否存在且指向真实文件。"""
    value = row.get(field_name)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    resolved = _resolve_path(output_root, text)
    exists = resolved.is_file()
    return PathCheck(
        field_name=field_name,
        value=text,
        resolved_path=resolved,
        exists=exists,
        byte_count=resolved.stat().st_size if exists else 0,
    )


def _required_output_checks(output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 attack 阶段必需输出文件是否存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in REQUIRED_ATTACK_OUTPUTS:
        path = output_root / relative
        exists = path.is_file()
        checks.append(
            {
                "relative_path": relative,
                "path": str(path),
                "exists": exists,
                "byte_count": path.stat().st_size if exists else 0,
            }
        )
        if not exists:
            issues.append({"issue_type": "missing_required_attack_output", "relative_path": relative})
    return checks, issues


def _attack_parameter_present(row: dict[str, Any]) -> bool:
    """检查 attack 参数字段是否存在, 兼容项目旧名和论文文档名。"""
    return row.get("attack_parameters") is not None or row.get("attack_params") is not None


def _build_attacked_record_checks(output_root: Path, payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """校验 attacked_image_manifest 中的 attacked image 记录。"""
    if not isinstance(payload, dict):
        return [], [{"issue_type": "attacked_manifest_not_object"}], 0
    records = payload.get("attacked_images")
    if not isinstance(records, list):
        return [], [{"issue_type": "attacked_images_not_list"}], 0
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw_row in enumerate(records):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "attacked_record_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        attacked_path = _path_check(output_root, row, "attacked_image_path")
        watermarked_path = _path_check(output_root, row, "watermarked_image_path")
        row_check = {
            "row_index": index,
            "attacked_image_id": row.get("attacked_image_id") or f"attacked_{index + 1:04d}",
            "attacked_image_path": attacked_path.to_dict() if attacked_path else None,
            "watermarked_image_path": watermarked_path.to_dict() if watermarked_path else None,
            "attack_family": row.get("attack_family"),
            "attack_condition": row.get("attack_condition"),
            "has_attack_parameters": _attack_parameter_present(row),
        }
        checks.append(row_check)
        for field in REQUIRED_ATTACK_RECORD_FIELDS:
            value = row.get(field)
            if value is None or str(value).strip() == "":
                issues.append({"issue_type": "missing_attack_record_field", "row_index": index, "field_name": field})
        if not _attack_parameter_present(row):
            issues.append({"issue_type": "missing_attack_parameters", "row_index": index})
        if attacked_path is not None and not attacked_path.exists:
            issues.append(
                {
                    "issue_type": "missing_attacked_image_file",
                    "row_index": index,
                    "path": str(attacked_path.resolved_path),
                }
            )
        if watermarked_path is not None and not watermarked_path.exists:
            issues.append(
                {
                    "issue_type": "missing_source_watermarked_image_file",
                    "row_index": index,
                    "path": str(watermarked_path.resolved_path),
                }
            )
    return checks, issues, len(records)


def _build_attacked_pair_checks(output_root: Path, payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """校验 image_pairs_attacked 是否可供 detection 阶段消费。"""
    if not isinstance(payload, list):
        return [], [{"issue_type": "image_pairs_attacked_not_list"}], 0
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw_row in enumerate(payload):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "attacked_pair_row_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        attacked_path = _path_check(output_root, row, "attacked_image_path") or _path_check(output_root, row, "attacked_path")
        row_check = {
            "row_index": index,
            "image_id": row.get("image_id") or row.get("event_id") or f"attacked_pair_{index + 1:04d}",
            "attacked_image": attacked_path.to_dict() if attacked_path else None,
            "attack_family": row.get("attack_family"),
            "attack_condition": row.get("attack_condition"),
        }
        checks.append(row_check)
        for field in ("attack_family", "attack_condition"):
            value = row.get(field)
            if value is None or str(value).strip() == "":
                issues.append({"issue_type": "missing_attacked_pair_field", "row_index": index, "field_name": field})
        if attacked_path is None:
            issues.append({"issue_type": "missing_attacked_pair_image_path", "row_index": index})
        elif not attacked_path.exists:
            issues.append(
                {
                    "issue_type": "missing_attacked_pair_image_file",
                    "row_index": index,
                    "path": str(attacked_path.resolved_path),
                }
            )
    return checks, issues, len(payload)


def _manifest_count(payload: Any, field_name: str) -> int | None:
    """从 manifest 中读取计数字段。"""
    if not isinstance(payload, dict):
        return None
    value = payload.get(field_name)
    if isinstance(value, int):
        return value
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_manifest_consistency_checks(
    attacked_manifest_payload: Any,
    shard_manifest_payload: Any,
    attacked_record_count: int,
    attacked_pair_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 attack manifest 计数和路径声明是否一致。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    attacked_count = _manifest_count(attacked_manifest_payload, "attacked_image_count")
    input_pair_count = _manifest_count(shard_manifest_payload, "input_image_pair_count")
    attacked_manifest_path = shard_manifest_payload.get("attacked_image_manifest_path") if isinstance(shard_manifest_payload, dict) else None
    attacked_pairs_path = shard_manifest_payload.get("attacked_image_pairs_path") if isinstance(shard_manifest_payload, dict) else None
    checks.append(
        {
            "check_name": "attacked_image_count_matches_records",
            "manifest_count": attacked_count,
            "record_count": attacked_record_count,
            "passes": attacked_count == attacked_record_count,
        }
    )
    checks.append(
        {
            "check_name": "attacked_pair_count_matches_records",
            "attacked_pair_count": attacked_pair_count,
            "attacked_record_count": attacked_record_count,
            "passes": attacked_pair_count == attacked_record_count,
        }
    )
    checks.append(
        {
            "check_name": "shard_manifest_declares_output_paths",
            "attacked_image_manifest_path": attacked_manifest_path,
            "attacked_image_pairs_path": attacked_pairs_path,
            "passes": bool(attacked_manifest_path) and bool(attacked_pairs_path),
        }
    )
    if attacked_count != attacked_record_count:
        issues.append(
            {
                "issue_type": "attacked_manifest_count_mismatch",
                "manifest_count": attacked_count,
                "record_count": attacked_record_count,
            }
        )
    if attacked_pair_count != attacked_record_count:
        issues.append(
            {
                "issue_type": "attacked_pair_count_mismatch",
                "attacked_pair_count": attacked_pair_count,
                "attacked_record_count": attacked_record_count,
            }
        )
    if not attacked_manifest_path or not attacked_pairs_path:
        issues.append({"issue_type": "shard_manifest_missing_output_path"})
    # input_pair_count 可以小于 attacked_record_count, 因为一个输入图像会产生多个 attack 条件。
    checks.append(
        {
            "check_name": "shard_input_pair_count_present",
            "input_image_pair_count": input_pair_count,
            "passes": input_pair_count is not None and input_pair_count >= 0,
        }
    )
    if input_pair_count is None or input_pair_count < 0:
        issues.append({"issue_type": "invalid_shard_input_image_pair_count", "input_image_pair_count": input_pair_count})
    return checks, issues


def build_pilot_attack_output_acceptance_report(output_root: str | Path) -> dict[str, Any]:
    """构建 attack 输出接收门禁报告。"""
    root = Path(output_root)
    required_checks, issues = _required_output_checks(root)
    attacked_manifest_path = root / "image_manifests" / "attacked_image_manifest.json"
    shard_manifest_path = root / "image_manifests" / "attack_shard_manifest.json"
    attacked_pairs_path = root / "image_pairs_attacked.json"
    attacked_manifest_payload, attacked_manifest_error = _read_json(attacked_manifest_path) if attacked_manifest_path.is_file() else (
        None,
        "missing_attacked_image_manifest",
    )
    shard_manifest_payload, shard_manifest_error = _read_json(shard_manifest_path) if shard_manifest_path.is_file() else (
        None,
        "missing_attack_shard_manifest",
    )
    attacked_pairs_payload, attacked_pairs_error = _read_json(attacked_pairs_path) if attacked_pairs_path.is_file() else (
        None,
        "missing_image_pairs_attacked",
    )
    if attacked_manifest_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_attacked_manifest", "path": str(attacked_manifest_path), "error": attacked_manifest_error})
    if shard_manifest_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_attack_shard_manifest", "path": str(shard_manifest_path), "error": shard_manifest_error})
    if attacked_pairs_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_image_pairs_attacked", "path": str(attacked_pairs_path), "error": attacked_pairs_error})
    attacked_record_checks, attacked_record_issues, attacked_record_count = _build_attacked_record_checks(
        root,
        attacked_manifest_payload,
    )
    attacked_pair_checks, attacked_pair_issues, attacked_pair_count = _build_attacked_pair_checks(root, attacked_pairs_payload)
    consistency_checks, consistency_issues = _build_manifest_consistency_checks(
        attacked_manifest_payload,
        shard_manifest_payload,
        attacked_record_count,
        attacked_pair_count,
    )
    issues.extend(attacked_record_issues)
    issues.extend(attacked_pair_issues)
    issues.extend(consistency_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "required_attack_outputs": list(REQUIRED_ATTACK_OUTPUTS),
        "required_output_checks": required_checks,
        "attacked_manifest_path": str(attacked_manifest_path),
        "attacked_manifest_readable_json": attacked_manifest_error is None,
        "attacked_manifest_json_error": attacked_manifest_error,
        "attack_shard_manifest_path": str(shard_manifest_path),
        "attack_shard_manifest_readable_json": shard_manifest_error is None,
        "attack_shard_manifest_json_error": shard_manifest_error,
        "image_pairs_attacked_path": str(attacked_pairs_path),
        "image_pairs_attacked_readable_json": attacked_pairs_error is None,
        "image_pairs_attacked_json_error": attacked_pairs_error,
        "attacked_record_checks": attacked_record_checks,
        "attacked_pair_checks": attacked_pair_checks,
        "manifest_consistency_checks": consistency_checks,
        "blocking_issues": issues,
        "summary": {
            "required_output_count": len(REQUIRED_ATTACK_OUTPUTS),
            "missing_required_output_count": sum(1 for item in required_checks if not item["exists"]),
            "attacked_record_count": attacked_record_count,
            "attacked_pair_count": attacked_pair_count,
            "attacked_record_check_count": len(attacked_record_checks),
            "attacked_pair_check_count": len(attacked_pair_checks),
            "manifest_consistency_check_count": len(consistency_checks),
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_attack_output_acceptance_report(output_root: str | Path, out: str | Path) -> dict[str, Any]:
    """写出 attack 输出接收门禁报告。"""
    report = build_pilot_attack_output_acceptance_report(output_root)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
