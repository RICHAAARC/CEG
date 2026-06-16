"""校验真实图像生成输出是否可进入后续论文流程。

该模块位于 experiments 层, 作用是接收外部 SD / watermark backend 已经写出的文件, 并检查
这些文件是否满足 attack、detection、quality metric 和 paper package 构建所需的最小契约。
它不运行 SD 模型, 不生成图像, 也不把 mock 输出声明为正式论文结果。

通用工程写法是: 对昂贵外部任务的输出建立接收门禁, 明确缺失文件、缺失字段和坏路径。
项目特定写法是: 该门禁固定检查 CEG 图像生成阶段约定的 prompt_plan、image_pairs 和
image_manifests, 并把结论写成可归档的 JSON 报告。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from experiments.image_generation_plan import REQUIRED_EXTERNAL_OUTPUTS, validate_image_generation_output_root

REPORT_NAME = "pilot_image_generation_output_acceptance_report.json"
NEXT_STAGE_ON_PASS = "image_attack_pilot"
NEXT_STAGE_ON_FAIL = "run_image_generation_backend_and_fix_outputs"


@dataclass(frozen=True)
class ResolvedImagePath:
    """表示从 image_pairs 记录中解析出的图像路径。"""

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


def _optional_string(row: dict[str, Any], *field_names: str) -> tuple[str | None, str | None]:
    """按候选字段顺序读取非空字符串。"""
    for field_name in field_names:
        value = row.get(field_name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return field_name, text
    return None, None


def _resolve_image_path(output_root: Path, value: str) -> Path:
    """把 image_pairs 中的相对路径解析到 output_root 下。"""
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return output_root / candidate


def _path_check(output_root: Path, row: dict[str, Any], candidates: tuple[str, ...]) -> ResolvedImagePath | None:
    """检查一组候选图像路径字段。"""
    field_name, value = _optional_string(row, *candidates)
    if field_name is None or value is None:
        return None
    resolved = _resolve_image_path(output_root, value)
    exists = resolved.is_file()
    return ResolvedImagePath(
        field_name=field_name,
        value=value,
        resolved_path=resolved,
        exists=exists,
        byte_count=resolved.stat().st_size if exists else 0,
    )


def _build_pair_checks(output_root: Path, image_pairs_payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """校验 image_pairs 记录中 clean / watermarked / attacked 图像路径。"""
    if not isinstance(image_pairs_payload, list):
        return [], [
            {
                "issue_type": "image_pairs_not_list",
                "message": "image_pairs.json must contain a list of image pair rows",
            }
        ], 0

    pair_checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw_row in enumerate(image_pairs_payload):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "image_pair_row_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        clean = _path_check(output_root, row, ("clean_image_path", "reference_path"))
        watermarked = _path_check(output_root, row, ("watermarked_image_path", "watermarked_path"))
        attacked = _path_check(output_root, row, ("attacked_image_path", "attacked_path"))
        row_check = {
            "row_index": index,
            "image_id": row.get("image_id") or row.get("event_id") or f"image_{index + 1:04d}",
            "clean_image": clean.to_dict() if clean else None,
            "watermarked_image": watermarked.to_dict() if watermarked else None,
            "attacked_image": attacked.to_dict() if attacked else None,
        }
        pair_checks.append(row_check)
        if clean is None:
            issues.append({"issue_type": "missing_clean_image_path_field", "row_index": index})
        elif not clean.exists:
            issues.append(
                {
                    "issue_type": "missing_clean_image_file",
                    "row_index": index,
                    "path": str(clean.resolved_path),
                }
            )
        if watermarked is None:
            issues.append({"issue_type": "missing_watermarked_image_path_field", "row_index": index})
        elif not watermarked.exists:
            issues.append(
                {
                    "issue_type": "missing_watermarked_image_file",
                    "row_index": index,
                    "path": str(watermarked.resolved_path),
                }
            )
        if attacked is not None and not attacked.exists:
            issues.append(
                {
                    "issue_type": "missing_attacked_image_file",
                    "row_index": index,
                    "path": str(attacked.resolved_path),
                }
            )
    return pair_checks, issues, len(image_pairs_payload)


def _manifest_count(payload: Any, count_field: str) -> int | None:
    """从 manifest 中读取样本计数字段。"""
    if not isinstance(payload, dict):
        return None
    value = payload.get(count_field)
    if isinstance(value, int):
        return value
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_manifest_checks(output_root: Path, image_pair_count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验图像生成 manifest 与 image pair manifest。"""
    manifest_specs = [
        {
            "relative_path": "image_manifests/image_generation_manifest.json",
            "count_field": "record_count",
            "count_label": "record_count",
        },
        {
            "relative_path": "image_manifests/image_pair_manifest.json",
            "count_field": "image_pair_count",
            "count_label": "image_pair_count",
        },
    ]
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in manifest_specs:
        path = output_root / spec["relative_path"]
        payload, error = _read_json(path) if path.is_file() else (None, "missing_manifest_file")
        count = _manifest_count(payload, str(spec["count_field"]))
        check = {
            "relative_path": spec["relative_path"],
            "path": str(path),
            "exists": path.is_file(),
            "readable_json": error is None,
            "json_error": error,
            "count_field": spec["count_field"],
            "count": count,
            "expected_image_pair_count": image_pair_count,
            "count_matches_image_pairs": count == image_pair_count if count is not None else False,
        }
        checks.append(check)
        if error is not None:
            issues.append({"issue_type": "unreadable_or_missing_manifest", "path": str(path), "error": error})
        elif count != image_pair_count:
            issues.append(
                {
                    "issue_type": "manifest_count_mismatch",
                    "path": str(path),
                    "count_field": spec["count_field"],
                    "count": count,
                    "expected_image_pair_count": image_pair_count,
                }
            )
    return checks, issues


def build_pilot_image_generation_output_acceptance_report(output_root: str | Path) -> dict[str, Any]:
    """构建图像生成输出接收门禁报告。"""
    root = Path(output_root)
    required_output_contract = validate_image_generation_output_root(root)
    image_pairs_path = root / "image_pairs.json"
    image_pairs_payload, image_pairs_error = _read_json(image_pairs_path) if image_pairs_path.is_file() else (
        None,
        "missing_image_pairs_file",
    )
    pair_checks, pair_issues, image_pair_count = _build_pair_checks(root, image_pairs_payload)
    manifest_checks, manifest_issues = _build_manifest_checks(root, image_pair_count)
    issues: list[dict[str, Any]] = []
    issues.extend(
        {"issue_type": "missing_required_output", "relative_path": relative}
        for relative in required_output_contract["missing_required_outputs"]
    )
    if image_pairs_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_image_pairs", "path": str(image_pairs_path), "error": image_pairs_error})
    issues.extend(pair_issues)
    issues.extend(manifest_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "required_external_outputs": list(REQUIRED_EXTERNAL_OUTPUTS),
        "required_output_contract": required_output_contract,
        "image_pairs_path": str(image_pairs_path),
        "image_pairs_readable_json": image_pairs_error is None,
        "image_pairs_json_error": image_pairs_error,
        "image_pair_checks": pair_checks,
        "manifest_checks": manifest_checks,
        "blocking_issues": issues,
        "summary": {
            "required_output_count": len(REQUIRED_EXTERNAL_OUTPUTS),
            "missing_required_output_count": len(required_output_contract["missing_required_outputs"]),
            "image_pair_count": image_pair_count,
            "image_pair_check_count": len(pair_checks),
            "manifest_check_count": len(manifest_checks),
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_image_generation_output_acceptance_report(output_root: str | Path, out: str | Path) -> dict[str, Any]:
    """写出图像生成输出接收门禁报告。"""
    report = build_pilot_image_generation_output_acceptance_report(output_root)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
