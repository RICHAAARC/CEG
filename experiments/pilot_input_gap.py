"""审计 pilot 输入从 rehearsal 进入真实 / 半真实 pilot 的缺口。

该模块只读取 `pilot_input_manifest.json` 及其声明的文件, 不生成正式论文结果。
它的职责是把当前输入包距离论文 pilot 所需输入的差距结构化记录下来,
使后续替换 dry-run fixture 为真实 SD / watermark / detection / baseline / metric 产物时有明确清单。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.pilot_input_manifest import load_pilot_input_manifest, validate_pilot_input_manifest

PILOT_INPUT_GAP_REPORT_NAME = "pilot_input_gap_report.json"

CORE_PILOT_FIELDS = (
    "events",
    "thresholds",
    "image_pairs",
    "attacked_image_manifest",
    "attack_shard_manifest",
    "baseline_observations",
    "baseline_execution_manifest",
    "metric_rows",
    "metric_execution_manifest",
    "detection_execution_manifest",
    "experiment_matrix",
    "readiness_requirements",
)

FORMAL_EVIDENCE_FIELDS = (
    "baseline_execution_manifest",
    "metric_execution_manifest",
    "detection_execution_manifest",
)


def _read_json(path: Path) -> Any:
    """按 UTF-8 读取 JSON 文件, 支持带 BOM 的外部导出文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _contains_dry_run_marker(value: Any) -> bool:
    """递归检查对象中是否存在 dry-run 语义标记。"""
    if isinstance(value, str):
        normalized = value.lower().replace("-", "_")
        return "dry_run" in normalized or "dryrun" in normalized or "mock_backend" in normalized
    if isinstance(value, dict):
        return any(_contains_dry_run_marker(key) or _contains_dry_run_marker(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_dry_run_marker(item) for item in value)
    return False


def _formal_claim_status(path: Path) -> dict[str, Any]:
    """检查 execution manifest 是否声明 formal_result_claim 和 evidence_paths。"""
    if not path.is_file():
        return {"status": "fail", "reason": "file_missing", "path": str(path)}
    try:
        payload = _read_json(path)
    except Exception as exc:  # noqa: BLE001 - 审计工具需要把解析错误写入报告。
        return {"status": "fail", "reason": "json_parse_failed", "path": str(path), "error": str(exc)}
    if not isinstance(payload, dict):
        return {"status": "fail", "reason": "manifest_not_object", "path": str(path)}
    evidence_paths = payload.get("evidence_paths", [])
    formal_claim = payload.get("formal_result_claim") is True
    evidence_count = len(evidence_paths) if isinstance(evidence_paths, list) else 0
    if formal_claim and evidence_count > 0:
        return {"status": "pass", "path": str(path), "formal_result_claim": True, "evidence_path_count": evidence_count}
    return {
        "status": "gap",
        "path": str(path),
        "formal_result_claim": formal_claim,
        "evidence_path_count": evidence_count,
        "reason": "formal_claim_or_evidence_paths_missing",
    }


def analyze_pilot_input_gap(manifest_path: str | Path, *, require_formal_claims: bool = False) -> dict[str, Any]:
    """分析一次 pilot 输入包距离真实论文 pilot 的缺口。

    通用工程写法:
    - 先复用已有 pilot input preflight, 避免重复实现路径和 schema 检查。
    - 再增加面向论文 pilot 的语义缺口检查, 包括缺失产物、dry-run 标记和 formal claim 证据。

    项目特定写法:
    - `CORE_PILOT_FIELDS` 对应 CEG 当前论文结果包需要的图像、攻击、检测、baseline、metric 和实验矩阵输入。
    - `require_formal_claims=True` 用于准备正式论文声明前的更严格检查。
    """
    path = Path(manifest_path)
    manifest = load_pilot_input_manifest(path)
    preflight = validate_pilot_input_manifest(path)
    resolved_inputs = preflight.get("resolved_inputs", {}) if isinstance(preflight, dict) else {}

    checks: list[dict[str, Any]] = []
    missing_core_fields: list[str] = []
    dry_run_fields: list[dict[str, Any]] = []

    for field in CORE_PILOT_FIELDS:
        resolved = resolved_inputs.get(field)
        if not resolved:
            checks.append({"requirement": "core_pilot_input_present", "field": field, "status": "gap", "reason": "field_absent"})
            missing_core_fields.append(field)
            continue
        candidate = Path(str(resolved))
        if not candidate.is_file():
            checks.append({"requirement": "core_pilot_input_present", "field": field, "status": "fail", "path": str(candidate), "reason": "file_missing"})
            missing_core_fields.append(field)
            continue
        checks.append({"requirement": "core_pilot_input_present", "field": field, "status": "pass", "path": str(candidate)})
        if candidate.suffix.lower() == ".json":
            try:
                payload = _read_json(candidate)
            except Exception as exc:  # noqa: BLE001 - 审计报告要保留错误细节。
                checks.append({"requirement": "dry_run_marker_absent", "field": field, "status": "fail", "path": str(candidate), "reason": str(exc)})
                continue
            if _contains_dry_run_marker(payload):
                item = {"field": field, "path": str(candidate), "reason": "dry_run_marker_present"}
                dry_run_fields.append(item)
                checks.append({"requirement": "dry_run_marker_absent", "status": "gap", **item})
            else:
                checks.append({"requirement": "dry_run_marker_absent", "field": field, "status": "pass", "path": str(candidate)})

    formal_claim_gaps: list[dict[str, Any]] = []
    for field in FORMAL_EVIDENCE_FIELDS:
        resolved = resolved_inputs.get(field)
        if not resolved:
            gap = {"field": field, "status": "gap", "reason": "execution_manifest_absent"}
        else:
            gap = {"field": field, **_formal_claim_status(Path(str(resolved)))}
        checks.append({"requirement": "formal_execution_evidence_ready", **gap})
        if gap.get("status") != "pass":
            formal_claim_gaps.append(gap)

    blocking_gap_count = len(missing_core_fields)
    if require_formal_claims:
        blocking_gap_count += len(formal_claim_gaps)
    readiness = "ready_for_formal_pilot" if blocking_gap_count == 0 and not dry_run_fields else "rehearsal_or_partial_pilot_only"

    return {
        "artifact_name": PILOT_INPUT_GAP_REPORT_NAME,
        "manifest_path": str(path),
        "overall_decision": "pass" if blocking_gap_count == 0 else "gap",
        "pilot_readiness_decision": readiness,
        "require_formal_claims": require_formal_claims,
        "preflight_decision": preflight.get("overall_decision"),
        "missing_core_fields": missing_core_fields,
        "dry_run_marker_fields": dry_run_fields,
        "formal_claim_gaps": formal_claim_gaps,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "blocking_gap_count": blocking_gap_count,
            "dry_run_marker_count": len(dry_run_fields),
            "formal_claim_gap_count": len(formal_claim_gaps),
        },
    }


def write_pilot_input_gap_report(
    manifest_path: str | Path,
    output_path: str | Path,
    *,
    require_formal_claims: bool = False,
) -> dict[str, Any]:
    """写出 pilot 输入缺口审计报告。"""
    report = analyze_pilot_input_gap(manifest_path, require_formal_claims=require_formal_claims)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
