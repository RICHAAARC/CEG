"""校验 external baseline pilot 输出是否可进入论文对比表和结果包构建。

该模块位于 experiments 层, 用于接收 baseline pilot producer、外部 baseline backend 或离线导入器
已经写出的 baseline 结果。它只检查 baseline observations、execution manifest 和可选 evidence
report 的契约, 不运行第三方 baseline 算法, 不重新计算分数, 也不把 dry-run baseline 声明为正式论文结果。

通用工程写法是: 在对比表构建前检查 observation rows 是否包含事件映射、baseline 标识、分数、阈值和分数方向。
项目特定写法是: 固定使用 CEG 论文结果包的 baseline_observations.json、baseline_execution_manifest.json
和 external_result_evidence_report.json 约定, 并把结论写成可归档的 JSON 门禁报告。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.baseline_pilot_producer import BASELINE_EXECUTION_MANIFEST_NAME, BASELINE_OBSERVATIONS_NAME
from experiments.external_result_evidence import EXTERNAL_RESULT_EVIDENCE_REPORT_NAME
from main.methods.baselines import BASELINE_REGISTRY

REPORT_NAME = "pilot_baseline_output_acceptance_report.json"
NEXT_STAGE_ON_PASS = "quality_metric_pilot"
NEXT_STAGE_ON_FAIL = "run_baseline_backend_and_fix_outputs"
REQUIRED_BASELINE_OUTPUTS = (BASELINE_OBSERVATIONS_NAME, BASELINE_EXECUTION_MANIFEST_NAME)
REQUIRED_OBSERVATION_FIELDS = (
    "event_id",
    "baseline_id",
    "score",
    "threshold",
    "higher_is_positive",
    "split",
    "sample_role",
    "attack_family",
    "attack_condition",
)


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _is_number(value: Any) -> bool:
    """判断值是否为数值, 显式排除 bool。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_bool(value: Any) -> bool | None:
    """读取布尔或常见字符串布尔值。"""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    return None


def _required_output_checks(output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 baseline 阶段必需输出文件是否存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in REQUIRED_BASELINE_OUTPUTS:
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
            issues.append({"issue_type": "missing_required_baseline_output", "relative_path": relative})
    return checks, issues


def _build_observation_checks(payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """校验 baseline_observations.json 的字段和分数可用性。"""
    if not isinstance(payload, list):
        return [], [{"issue_type": "baseline_observations_not_list"}], {
            "observation_count": 0,
            "baseline_ids": [],
            "event_count": 0,
            "test_observation_count": 0,
            "attacked_observation_count": 0,
            "registered_baseline_count": 0,
            "unregistered_baseline_count": 0,
        }
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    baseline_ids: set[str] = set()
    event_ids: set[str] = set()
    test_count = 0
    attacked_count = 0
    for index, raw_row in enumerate(payload):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "baseline_observation_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        baseline_id = str(row.get("baseline_id") or "").strip()
        event_id = str(row.get("event_id") or "").strip()
        if baseline_id:
            baseline_ids.add(baseline_id)
        if event_id:
            event_ids.add(event_id)
        if str(row.get("split") or "") == "test":
            test_count += 1
        if str(row.get("attack_family") or "clean") != "clean":
            attacked_count += 1
        missing_fields = [
            field for field in REQUIRED_OBSERVATION_FIELDS if row.get(field) is None or str(row.get(field)).strip() == ""
        ]
        score_is_number = _is_number(row.get("score"))
        threshold_is_number = _is_number(row.get("threshold"))
        direction = _as_bool(row.get("higher_is_positive"))
        row_check = {
            "row_index": index,
            "event_id": event_id or None,
            "baseline_id": baseline_id or None,
            "baseline_registered": baseline_id in BASELINE_REGISTRY,
            "score": row.get("score"),
            "score_is_numeric": score_is_number,
            "threshold": row.get("threshold"),
            "threshold_is_numeric": threshold_is_number,
            "higher_is_positive_is_bool_like": direction is not None,
            "missing_fields": missing_fields,
        }
        checks.append(row_check)
        for field in missing_fields:
            issues.append({"issue_type": "missing_baseline_observation_field", "row_index": index, "field_name": field})
        if baseline_id and baseline_id not in BASELINE_REGISTRY:
            issues.append({"issue_type": "unregistered_baseline_id", "row_index": index, "baseline_id": baseline_id})
        if not score_is_number:
            issues.append({"issue_type": "non_numeric_baseline_score", "row_index": index})
        if not threshold_is_number:
            issues.append({"issue_type": "non_numeric_baseline_threshold", "row_index": index})
        if direction is None:
            issues.append({"issue_type": "invalid_higher_is_positive", "row_index": index})
    registered_count = sum(1 for baseline_id in baseline_ids if baseline_id in BASELINE_REGISTRY)
    unregistered_count = len(baseline_ids) - registered_count
    if not payload:
        issues.append({"issue_type": "empty_baseline_observations"})
    if not baseline_ids:
        issues.append({"issue_type": "no_baseline_ids"})
    return checks, issues, {
        "observation_count": len(payload),
        "baseline_ids": sorted(baseline_ids),
        "event_count": len(event_ids),
        "test_observation_count": test_count,
        "attacked_observation_count": attacked_count,
        "registered_baseline_count": registered_count,
        "unregistered_baseline_count": unregistered_count,
    }


def _build_manifest_checks(manifest_payload: Any, observation_summary: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验 baseline_execution_manifest 与 observations 的一致性。"""
    if not isinstance(manifest_payload, dict):
        return [], [{"issue_type": "baseline_execution_manifest_not_object"}]
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    expected_name = BASELINE_EXECUTION_MANIFEST_NAME
    artifact_name = manifest_payload.get("artifact_name")
    manifest_observation_count = manifest_payload.get("observation_count")
    manifest_baseline_ids = manifest_payload.get("baseline_ids")
    if not isinstance(manifest_baseline_ids, list):
        manifest_baseline_ids = []
        issues.append({"issue_type": "manifest_baseline_ids_not_list"})
    observed_ids = list(observation_summary["baseline_ids"])
    checks.append(
        {
            "check_name": "artifact_name_matches",
            "expected": expected_name,
            "actual": artifact_name,
            "passes": artifact_name == expected_name,
        }
    )
    checks.append(
        {
            "check_name": "observation_count_matches",
            "manifest_observation_count": manifest_observation_count,
            "observed_observation_count": observation_summary["observation_count"],
            "passes": manifest_observation_count == observation_summary["observation_count"],
        }
    )
    checks.append(
        {
            "check_name": "baseline_ids_match_observations",
            "manifest_baseline_ids": sorted(str(item) for item in manifest_baseline_ids),
            "observed_baseline_ids": observed_ids,
            "passes": sorted(str(item) for item in manifest_baseline_ids) == observed_ids,
        }
    )
    for field in ("producer_id", "producer_role", "formal_result_claim", "baseline_observations_path"):
        present = field in manifest_payload and manifest_payload.get(field) not in {None, ""}
        checks.append({"check_name": f"manifest_field_present_{field}", "passes": present, "value": manifest_payload.get(field)})
        if not present:
            issues.append({"issue_type": "missing_baseline_manifest_field", "field_name": field})
    if artifact_name != expected_name:
        issues.append({"issue_type": "unexpected_baseline_manifest_artifact_name", "expected": expected_name, "actual": artifact_name})
    if manifest_observation_count != observation_summary["observation_count"]:
        issues.append(
            {
                "issue_type": "baseline_manifest_observation_count_mismatch",
                "manifest_observation_count": manifest_observation_count,
                "observed_observation_count": observation_summary["observation_count"],
            }
        )
    if sorted(str(item) for item in manifest_baseline_ids) != observed_ids:
        issues.append({"issue_type": "baseline_manifest_ids_mismatch"})
    return checks, issues


def _build_evidence_checks(output_root: Path, *, require_formal_evidence: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验可选 external_result_evidence_report。"""
    path = output_root / EXTERNAL_RESULT_EVIDENCE_REPORT_NAME
    payload, error = _read_json(path) if path.is_file() else (None, "missing_external_result_evidence_report")
    check = {
        "relative_path": EXTERNAL_RESULT_EVIDENCE_REPORT_NAME,
        "path": str(path),
        "exists": path.is_file(),
        "readable_json": error is None,
        "json_error": error,
        "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
        "require_formal_evidence": require_formal_evidence,
    }
    issues: list[dict[str, Any]] = []
    if require_formal_evidence:
        if error is not None:
            issues.append({"issue_type": "missing_required_external_evidence_report", "error": error})
        elif not isinstance(payload, dict) or payload.get("overall_decision") != "pass":
            issues.append({"issue_type": "external_evidence_report_not_pass", "overall_decision": check["overall_decision"]})
    return [check], issues


def build_pilot_baseline_output_acceptance_report(
    output_root: str | Path,
    *,
    require_formal_evidence: bool = False,
) -> dict[str, Any]:
    """构建 external baseline 输出接收门禁报告。"""
    root = Path(output_root)
    required_checks, issues = _required_output_checks(root)
    observations_path = root / BASELINE_OBSERVATIONS_NAME
    manifest_path = root / BASELINE_EXECUTION_MANIFEST_NAME
    observations_payload, observations_error = _read_json(observations_path) if observations_path.is_file() else (
        None,
        "missing_baseline_observations",
    )
    manifest_payload, manifest_error = _read_json(manifest_path) if manifest_path.is_file() else (
        None,
        "missing_baseline_execution_manifest",
    )
    if observations_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_baseline_observations", "path": str(observations_path), "error": observations_error})
    if manifest_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_baseline_execution_manifest", "path": str(manifest_path), "error": manifest_error})
    observation_checks, observation_issues, observation_summary = _build_observation_checks(observations_payload)
    manifest_checks, manifest_issues = _build_manifest_checks(manifest_payload, observation_summary)
    evidence_checks, evidence_issues = _build_evidence_checks(root, require_formal_evidence=require_formal_evidence)
    issues.extend(observation_issues)
    issues.extend(manifest_issues)
    issues.extend(evidence_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "require_formal_evidence": bool(require_formal_evidence),
        "required_baseline_outputs": list(REQUIRED_BASELINE_OUTPUTS),
        "required_output_checks": required_checks,
        "observations_path": str(observations_path),
        "observations_readable_json": observations_error is None,
        "observations_json_error": observations_error,
        "execution_manifest_path": str(manifest_path),
        "execution_manifest_readable_json": manifest_error is None,
        "execution_manifest_json_error": manifest_error,
        "observation_checks": observation_checks,
        "manifest_checks": manifest_checks,
        "evidence_checks": evidence_checks,
        "observation_summary": observation_summary,
        "blocking_issues": issues,
        "summary": {
            "missing_required_output_count": sum(1 for item in required_checks if not item["exists"]),
            "observation_count": observation_summary["observation_count"],
            "baseline_count": len(observation_summary["baseline_ids"]),
            "event_count": observation_summary["event_count"],
            "observation_check_count": len(observation_checks),
            "manifest_check_count": len(manifest_checks),
            "evidence_check_count": len(evidence_checks),
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_baseline_output_acceptance_report(
    output_root: str | Path,
    out: str | Path,
    *,
    require_formal_evidence: bool = False,
) -> dict[str, Any]:
    """写出 external baseline 输出接收门禁报告。"""
    report = build_pilot_baseline_output_acceptance_report(output_root, require_formal_evidence=require_formal_evidence)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
