"""校验 quality metric pilot 输出是否可进入论文质量表和结果包构建。

该模块位于 experiments 层, 用于接收轻量 metric runner、外部高级 metric backend 或离线导入器
已经写出的 metric 结果。它只检查 metric rows、execution manifest 和可选 evidence report 的契约,
不运行 LPIPS、FID、CLIP score 等重型模型, 也不把 dry-run metric 声明为正式论文结果。

通用工程写法是: 在论文质量表构建前确认 metric rows 具备样本身份、指标字段和数值可用性。
项目特定写法是: 固定使用 metric_rows.json、metric_execution_manifest.json 和
external_result_evidence_report.json 约定, 并把结论写成可归档的 JSON 门禁报告。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.external_result_evidence import EXTERNAL_RESULT_EVIDENCE_REPORT_NAME
from experiments.metric_file_adapter import METRIC_ROW_IMPORT_MANIFEST_NAME, STANDARD_METRIC_COLUMNS, load_metric_rows

REPORT_NAME = "pilot_metric_output_acceptance_report.json"
METRIC_ROWS_NAME = "metric_rows.json"
METRIC_SUMMARY_TABLE_NAME = "quality_metric_summary_table.csv"
NEXT_STAGE_ON_PASS = "fixed_fpr_statistics_pilot"
NEXT_STAGE_ON_FAIL = "run_metric_backend_and_fix_outputs"
REQUIRED_METRIC_OUTPUTS = (METRIC_ROWS_NAME, METRIC_ROW_IMPORT_MANIFEST_NAME)
IDENTITY_FIELDS = ("event_id", "method_name", "baseline_id")
PROVENANCE_FIELDS = ("event_id", "sample_id", "image_id", "source_image", "clean_image_path", "watermarked_image_path")


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _is_number(value: Any) -> bool:
    """判断值是否为数值, 显式排除 bool。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _required_output_checks(output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 metric 阶段必须输出文件是否存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in REQUIRED_METRIC_OUTPUTS:
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
            issues.append({"issue_type": "missing_required_metric_output", "relative_path": relative})
    return checks, issues


def _summary_table_check(output_root: Path) -> dict[str, Any]:
    """检查可选质量指标汇总表是否存在, 该检查不阻断最小接收门禁。"""
    path = output_root / METRIC_SUMMARY_TABLE_NAME
    return {
        "relative_path": METRIC_SUMMARY_TABLE_NAME,
        "path": str(path),
        "exists": path.is_file(),
        "byte_count": path.stat().st_size if path.is_file() else 0,
        "blocking": False,
    }


def _build_metric_row_checks(rows: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """校验 metric_rows.json 的字段、数值和 provenance 可用性。"""
    if not isinstance(rows, list):
        return [], [{"issue_type": "metric_rows_not_list"}], {
            "metric_row_count": 0,
            "metric_fields": [],
            "advanced_metric_fields": [],
            "method_names": [],
            "baseline_ids": [],
            "event_count": 0,
        }

    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    metric_fields: set[str] = set()
    advanced_metric_fields: set[str] = set()
    method_names: set[str] = set()
    baseline_ids: set[str] = set()
    event_ids: set[str] = set()

    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            issues.append({"issue_type": "metric_row_not_object", "row_index": index})
            continue
        row = dict(raw_row)
        row_metric_fields = [field for field in sorted(STANDARD_METRIC_COLUMNS) if field in row and row.get(field) is not None]
        numeric_metric_fields = [field for field in row_metric_fields if _is_number(row.get(field))]
        non_numeric_metric_fields = [field for field in row_metric_fields if not _is_number(row.get(field))]
        provenance_fields = [field for field in PROVENANCE_FIELDS if row.get(field) not in {None, ""}]
        identity_fields = [field for field in IDENTITY_FIELDS if row.get(field) not in {None, ""}]

        metric_fields.update(row_metric_fields)
        advanced_metric_fields.update({"lpips", "fid", "clip_score"} & set(row_metric_fields))
        if row.get("method_name"):
            method_names.add(str(row["method_name"]))
        if row.get("baseline_id"):
            baseline_ids.add(str(row["baseline_id"]))
        if row.get("event_id"):
            event_ids.add(str(row["event_id"]))

        checks.append(
            {
                "row_index": index,
                "event_id": row.get("event_id"),
                "method_name": row.get("method_name"),
                "baseline_id": row.get("baseline_id"),
                "metric_fields": row_metric_fields,
                "numeric_metric_fields": numeric_metric_fields,
                "non_numeric_metric_fields": non_numeric_metric_fields,
                "identity_fields": identity_fields,
                "provenance_fields": provenance_fields,
            }
        )
        if not row_metric_fields:
            issues.append({"issue_type": "metric_row_has_no_supported_metric_fields", "row_index": index})
        for field in non_numeric_metric_fields:
            issues.append({"issue_type": "non_numeric_metric_value", "row_index": index, "field_name": field})
        if not identity_fields:
            issues.append({"issue_type": "metric_row_missing_identity", "row_index": index})
        if not provenance_fields:
            issues.append({"issue_type": "metric_row_missing_provenance", "row_index": index})

    if not rows:
        issues.append({"issue_type": "empty_metric_rows"})
    if not metric_fields:
        issues.append({"issue_type": "no_supported_metric_fields"})

    return checks, issues, {
        "metric_row_count": len(rows),
        "metric_fields": sorted(metric_fields),
        "advanced_metric_fields": sorted(advanced_metric_fields),
        "method_names": sorted(method_names),
        "baseline_ids": sorted(baseline_ids),
        "event_count": len(event_ids),
    }


def _build_manifest_checks(manifest_payload: Any, metric_summary: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验 metric_execution_manifest 与 metric rows 的一致性。"""
    if not isinstance(manifest_payload, dict):
        return [], [{"issue_type": "metric_execution_manifest_not_object"}]

    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    expected_name = METRIC_ROW_IMPORT_MANIFEST_NAME
    artifact_name = manifest_payload.get("artifact_name")
    manifest_metric_row_count = manifest_payload.get("metric_row_count")
    manifest_metric_fields = manifest_payload.get("metric_fields")
    if not isinstance(manifest_metric_fields, list):
        manifest_metric_fields = []
        issues.append({"issue_type": "manifest_metric_fields_not_list"})

    observed_metric_fields = list(metric_summary["metric_fields"])
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
            "check_name": "metric_row_count_matches",
            "manifest_metric_row_count": manifest_metric_row_count,
            "observed_metric_row_count": metric_summary["metric_row_count"],
            "passes": manifest_metric_row_count == metric_summary["metric_row_count"],
        }
    )
    checks.append(
        {
            "check_name": "metric_fields_match_rows",
            "manifest_metric_fields": sorted(str(item) for item in manifest_metric_fields),
            "observed_metric_fields": observed_metric_fields,
            "passes": sorted(str(item) for item in manifest_metric_fields) == observed_metric_fields,
        }
    )
    for field in ("producer_id", "producer_role", "formal_result_claim", "metric_rows_path"):
        present = field in manifest_payload and manifest_payload.get(field) not in {None, ""}
        checks.append({"check_name": f"manifest_field_present_{field}", "passes": present, "value": manifest_payload.get(field)})
        if not present:
            issues.append({"issue_type": "missing_metric_manifest_field", "field_name": field})
    if artifact_name != expected_name:
        issues.append({"issue_type": "unexpected_metric_manifest_artifact_name", "expected": expected_name, "actual": artifact_name})
    if manifest_metric_row_count != metric_summary["metric_row_count"]:
        issues.append(
            {
                "issue_type": "metric_manifest_row_count_mismatch",
                "manifest_metric_row_count": manifest_metric_row_count,
                "observed_metric_row_count": metric_summary["metric_row_count"],
            }
        )
    if sorted(str(item) for item in manifest_metric_fields) != observed_metric_fields:
        issues.append({"issue_type": "metric_manifest_fields_mismatch"})
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


def build_pilot_metric_output_acceptance_report(
    output_root: str | Path,
    *,
    require_formal_evidence: bool = False,
) -> dict[str, Any]:
    """构建 quality metric 输出接收门禁报告。"""
    root = Path(output_root)
    required_checks, issues = _required_output_checks(root)
    rows_path = root / METRIC_ROWS_NAME
    manifest_path = root / METRIC_ROW_IMPORT_MANIFEST_NAME
    rows_payload, rows_error = _read_json(rows_path) if rows_path.is_file() else (None, "missing_metric_rows")
    manifest_payload, manifest_error = _read_json(manifest_path) if manifest_path.is_file() else (None, "missing_metric_execution_manifest")

    normalized_rows: list[dict[str, Any]] | None = None
    normalized_rows_error: str | None = None
    if rows_error is None:
        try:
            normalized_rows = load_metric_rows(rows_path)
        except Exception as exc:  # pragma: no cover - 具体错误由 adapter 决定
            normalized_rows_error = f"{type(exc).__name__}: {exc}"
            issues.append({"issue_type": "metric_rows_adapter_normalization_failed", "error": normalized_rows_error})

    if rows_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_metric_rows", "path": str(rows_path), "error": rows_error})
    if manifest_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_metric_execution_manifest", "path": str(manifest_path), "error": manifest_error})

    row_checks, row_issues, metric_summary = _build_metric_row_checks(normalized_rows if normalized_rows is not None else rows_payload)
    manifest_checks, manifest_issues = _build_manifest_checks(manifest_payload, metric_summary)
    evidence_checks, evidence_issues = _build_evidence_checks(root, require_formal_evidence=require_formal_evidence)
    summary_table_check = _summary_table_check(root)

    issues.extend(row_issues)
    issues.extend(manifest_issues)
    issues.extend(evidence_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "require_formal_evidence": bool(require_formal_evidence),
        "required_metric_outputs": list(REQUIRED_METRIC_OUTPUTS),
        "required_output_checks": required_checks,
        "summary_table_check": summary_table_check,
        "metric_rows_path": str(rows_path),
        "metric_rows_readable_json": rows_error is None,
        "metric_rows_json_error": rows_error,
        "metric_rows_adapter_normalization_error": normalized_rows_error,
        "execution_manifest_path": str(manifest_path),
        "execution_manifest_readable_json": manifest_error is None,
        "execution_manifest_json_error": manifest_error,
        "metric_row_checks": row_checks,
        "manifest_checks": manifest_checks,
        "evidence_checks": evidence_checks,
        "metric_summary": metric_summary,
        "blocking_issues": issues,
        "summary": {
            "missing_required_output_count": sum(1 for item in required_checks if not item["exists"]),
            "metric_row_count": metric_summary["metric_row_count"],
            "metric_field_count": len(metric_summary["metric_fields"]),
            "advanced_metric_field_count": len(metric_summary["advanced_metric_fields"]),
            "method_count": len(metric_summary["method_names"]),
            "baseline_count": len(metric_summary["baseline_ids"]),
            "event_count": metric_summary["event_count"],
            "metric_row_check_count": len(row_checks),
            "manifest_check_count": len(manifest_checks),
            "evidence_check_count": len(evidence_checks),
            "summary_table_exists": summary_table_check["exists"],
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_metric_output_acceptance_report(
    output_root: str | Path,
    out: str | Path,
    *,
    require_formal_evidence: bool = False,
) -> dict[str, Any]:
    """写出 quality metric 输出接收门禁报告。"""
    report = build_pilot_metric_output_acceptance_report(output_root, require_formal_evidence=require_formal_evidence)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
