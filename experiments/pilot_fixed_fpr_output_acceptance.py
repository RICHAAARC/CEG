"""校验 fixed-FPR / TPR@FPR 统计输出是否可进入论文主表和结果包构建。

该模块位于 experiments 层, 用于接收 `main.analysis.fixed_fpr` 或 `build_paper_outputs.py`
已经重建出的统计表。它只检查 CSV 表格契约和统计口径, 不重新运行 detector, 不重新选择
实验阈值, 也不把 dry-run 表格声明为正式论文结果。

通用工程写法是: 在论文表格使用前检查阈值表、TPR 表、attack TPR 表和 baseline 对比表是否
字段完整、数值可解析、target FPR 对齐。项目特定写法是: 强制要求 calibration clean negative
作为阈值来源, 防止使用 test split 或 fallback 负例支撑论文 claim。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPORT_NAME = "pilot_fixed_fpr_output_acceptance_report.json"
NEXT_STAGE_ON_PASS = "paper_result_package_pilot"
NEXT_STAGE_ON_FAIL = "run_fixed_fpr_statistics_and_fix_outputs"

FIXED_FPR_THRESHOLD_TABLE_NAME = "fixed_fpr_threshold_table.csv"
TPR_AT_FIXED_FPR_TABLE_NAME = "tpr_at_fixed_fpr_table.csv"
ATTACK_TPR_AT_FIXED_FPR_TABLE_NAME = "attack_tpr_at_fixed_fpr_table.csv"
BASELINE_COMPARISON_TABLE_NAME = "baseline_comparison_table.csv"
STATISTICAL_TEST_REPORT_NAME = "statistical_test_report.json"

REQUIRED_FIXED_FPR_OUTPUTS = (
    FIXED_FPR_THRESHOLD_TABLE_NAME,
    TPR_AT_FIXED_FPR_TABLE_NAME,
    ATTACK_TPR_AT_FIXED_FPR_TABLE_NAME,
    BASELINE_COMPARISON_TABLE_NAME,
)
REQUIRED_COLUMNS = {
    FIXED_FPR_THRESHOLD_TABLE_NAME: (
        "method_name",
        "target_fpr",
        "threshold_value",
        "calibration_source",
        "calibration_negative_count",
        "calibration_observed_fpr",
    ),
    TPR_AT_FIXED_FPR_TABLE_NAME: (
        "method_name",
        "target_fpr",
        "threshold_value",
        "test_clean_negative_count",
        "test_fpr_at_threshold",
        "test_positive_count",
        "tpr_at_fixed_fpr",
    ),
    ATTACK_TPR_AT_FIXED_FPR_TABLE_NAME: (
        "method_name",
        "target_fpr",
        "threshold_value",
        "attack_family",
        "attacked_positive_count",
        "attack_tpr_at_fixed_fpr",
    ),
    BASELINE_COMPARISON_TABLE_NAME: ("method_name",),
}
RATE_COLUMNS = {
    "target_fpr",
    "calibration_observed_fpr",
    "test_fpr_at_threshold",
    "tpr_at_fixed_fpr",
    "attack_tpr_at_fixed_fpr",
}
COUNT_COLUMNS = {
    "calibration_negative_count",
    "calibration_false_positive_count",
    "test_clean_negative_count",
    "test_false_positive_count",
    "test_positive_count",
    "test_true_positive_count",
    "attacked_positive_count",
    "attacked_true_positive_count",
}
NUMERIC_COLUMNS = RATE_COLUMNS | COUNT_COLUMNS | {"threshold_value"}


def _read_csv(path: Path) -> tuple[list[dict[str, str]] | None, str | None]:
    """读取 CSV 表格, 返回行列表与错误信息。"""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)], None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 IO / CSV 决定
        return None, f"{type(exc).__name__}: {exc}"


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _to_float(value: Any) -> float | None:
    """把 CSV 字段转换为 float, 空值返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"none", "null", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_non_negative_integer_text(value: Any) -> bool:
    """判断 CSV 字段是否表示非负整数。"""
    number = _to_float(value)
    return number is not None and number >= 0 and number.is_integer()


def _required_output_checks(output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 fixed-FPR 阶段必须输出文件是否存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in REQUIRED_FIXED_FPR_OUTPUTS:
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
            issues.append({"issue_type": "missing_required_fixed_fpr_output", "relative_path": relative})
    return checks, issues


def _build_table_checks(table_name: str, rows: list[dict[str, str]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """校验单个 fixed-FPR 统计表的列、数值和基本行级契约。"""
    required_columns = REQUIRED_COLUMNS[table_name]
    if rows is None:
        return [], [{"issue_type": "fixed_fpr_table_unreadable", "table_name": table_name}], {
            "row_count": 0,
            "method_names": [],
            "target_fprs": [],
        }
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    method_names: set[str] = set()
    target_fprs: set[float] = set()

    if not rows:
        issues.append({"issue_type": "empty_fixed_fpr_table", "table_name": table_name})

    for index, row in enumerate(rows):
        method_name = str(row.get("method_name") or "").strip()
        if method_name:
            method_names.add(method_name)
        target_fpr = _to_float(row.get("target_fpr")) if "target_fpr" in row else None
        if target_fpr is not None:
            target_fprs.add(target_fpr)
        missing_columns = [column for column in required_columns if column not in row or str(row.get(column) or "").strip() == ""]
        non_numeric_columns = [
            column
            for column in NUMERIC_COLUMNS
            if column in row and str(row.get(column) or "").strip() != "" and _to_float(row.get(column)) is None
        ]
        out_of_range_rate_columns = []
        for column in RATE_COLUMNS:
            if column in row and str(row.get(column) or "").strip() != "":
                number = _to_float(row.get(column))
                if number is not None and not 0 <= number <= 1:
                    out_of_range_rate_columns.append(column)
        invalid_count_columns = [
            column
            for column in COUNT_COLUMNS
            if column in row and str(row.get(column) or "").strip() != "" and not _is_non_negative_integer_text(row.get(column))
        ]
        checks.append(
            {
                "table_name": table_name,
                "row_index": index,
                "method_name": method_name or None,
                "target_fpr": target_fpr,
                "missing_columns": missing_columns,
                "non_numeric_columns": non_numeric_columns,
                "out_of_range_rate_columns": out_of_range_rate_columns,
                "invalid_count_columns": invalid_count_columns,
            }
        )
        for column in missing_columns:
            issues.append({"issue_type": "missing_fixed_fpr_column", "table_name": table_name, "row_index": index, "column_name": column})
        for column in non_numeric_columns:
            issues.append({"issue_type": "non_numeric_fixed_fpr_value", "table_name": table_name, "row_index": index, "column_name": column})
        for column in out_of_range_rate_columns:
            issues.append({"issue_type": "fixed_fpr_rate_out_of_range", "table_name": table_name, "row_index": index, "column_name": column})
        for column in invalid_count_columns:
            issues.append({"issue_type": "invalid_fixed_fpr_count", "table_name": table_name, "row_index": index, "column_name": column})
        if not method_name:
            issues.append({"issue_type": "missing_fixed_fpr_method_name", "table_name": table_name, "row_index": index})

    return checks, issues, {
        "row_count": len(rows),
        "method_names": sorted(method_names),
        "target_fprs": sorted(target_fprs),
    }


def _build_cross_table_checks(table_summaries: dict[str, dict[str, Any]], table_rows: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验 threshold, TPR 和 attack TPR 表之间的 method / target FPR 对齐关系。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    threshold_pairs = {
        (str(row.get("method_name")), _to_float(row.get("target_fpr")))
        for row in table_rows.get(FIXED_FPR_THRESHOLD_TABLE_NAME, [])
        if row.get("method_name") and _to_float(row.get("target_fpr")) is not None
    }
    tpr_pairs = {
        (str(row.get("method_name")), _to_float(row.get("target_fpr")))
        for row in table_rows.get(TPR_AT_FIXED_FPR_TABLE_NAME, [])
        if row.get("method_name") and _to_float(row.get("target_fpr")) is not None
    }
    attack_pairs = {
        (str(row.get("method_name")), _to_float(row.get("target_fpr")))
        for row in table_rows.get(ATTACK_TPR_AT_FIXED_FPR_TABLE_NAME, [])
        if row.get("method_name") and _to_float(row.get("target_fpr")) is not None
    }
    missing_tpr_pairs = sorted(threshold_pairs - tpr_pairs)
    attack_without_threshold = sorted(attack_pairs - threshold_pairs)
    checks.append(
        {
            "check_name": "threshold_pairs_have_tpr_rows",
            "threshold_pair_count": len(threshold_pairs),
            "tpr_pair_count": len(tpr_pairs),
            "missing_tpr_pairs": missing_tpr_pairs,
            "passes": not missing_tpr_pairs,
        }
    )
    checks.append(
        {
            "check_name": "attack_pairs_are_subset_of_threshold_pairs",
            "attack_pair_count": len(attack_pairs),
            "attack_without_threshold": attack_without_threshold,
            "passes": not attack_without_threshold,
        }
    )
    if missing_tpr_pairs:
        issues.append({"issue_type": "fixed_fpr_threshold_without_tpr_row", "pairs": missing_tpr_pairs})
    if attack_without_threshold:
        issues.append({"issue_type": "attack_tpr_without_threshold_row", "pairs": attack_without_threshold})

    baseline_methods = set(table_summaries.get(BASELINE_COMPARISON_TABLE_NAME, {}).get("method_names", []))
    tpr_methods = set(table_summaries.get(TPR_AT_FIXED_FPR_TABLE_NAME, {}).get("method_names", []))
    missing_baseline_methods = sorted(tpr_methods - baseline_methods)
    checks.append(
        {
            "check_name": "baseline_table_covers_tpr_methods",
            "baseline_methods": sorted(baseline_methods),
            "tpr_methods": sorted(tpr_methods),
            "missing_baseline_methods": missing_baseline_methods,
            "passes": not missing_baseline_methods,
        }
    )
    if missing_baseline_methods:
        issues.append({"issue_type": "baseline_comparison_missing_tpr_methods", "method_names": missing_baseline_methods})
    return checks, issues


def _build_calibration_source_checks(threshold_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """要求论文 fixed-FPR 阈值来源必须是 calibration clean negative。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, row in enumerate(threshold_rows):
        source = str(row.get("calibration_source") or "").strip()
        passes = source == "calibration_clean_negative"
        checks.append({"row_index": index, "calibration_source": source, "passes": passes})
        if not passes:
            issues.append({"issue_type": "non_calibration_threshold_source", "row_index": index, "calibration_source": source})
    return checks, issues


def _build_statistical_report_check(output_root: Path, *, require_statistical_report: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """检查可选 statistical_test_report.json。"""
    path = output_root / STATISTICAL_TEST_REPORT_NAME
    payload, error = _read_json(path) if path.is_file() else (None, "missing_statistical_test_report")
    check = {
        "relative_path": STATISTICAL_TEST_REPORT_NAME,
        "path": str(path),
        "exists": path.is_file(),
        "readable_json": error is None,
        "json_error": error,
        "require_statistical_report": require_statistical_report,
        "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
    }
    issues: list[dict[str, Any]] = []
    if require_statistical_report:
        if error is not None:
            issues.append({"issue_type": "missing_required_statistical_test_report", "error": error})
        elif not isinstance(payload, dict):
            issues.append({"issue_type": "statistical_test_report_not_object"})
    return check, issues


def build_pilot_fixed_fpr_output_acceptance_report(
    output_root: str | Path,
    *,
    require_statistical_report: bool = False,
) -> dict[str, Any]:
    """构建 fixed-FPR / TPR@FPR 统计输出接收门禁报告。"""
    root = Path(output_root)
    required_checks, issues = _required_output_checks(root)
    table_rows: dict[str, list[dict[str, str]]] = {}
    table_checks: dict[str, list[dict[str, Any]]] = {}
    table_summaries: dict[str, dict[str, Any]] = {}
    table_json_errors: dict[str, str | None] = {}
    for table_name in REQUIRED_FIXED_FPR_OUTPUTS:
        path = root / table_name
        rows, error = _read_csv(path) if path.is_file() else (None, f"missing_{table_name}")
        table_json_errors[table_name] = error
        if error is not None:
            issues.append({"issue_type": "unreadable_or_missing_fixed_fpr_table", "table_name": table_name, "path": str(path), "error": error})
        checks, row_issues, summary = _build_table_checks(table_name, rows)
        table_rows[table_name] = rows or []
        table_checks[table_name] = checks
        table_summaries[table_name] = summary
        issues.extend(row_issues)

    calibration_checks, calibration_issues = _build_calibration_source_checks(table_rows.get(FIXED_FPR_THRESHOLD_TABLE_NAME, []))
    cross_table_checks, cross_table_issues = _build_cross_table_checks(table_summaries, table_rows)
    statistical_report_check, statistical_issues = _build_statistical_report_check(
        root,
        require_statistical_report=require_statistical_report,
    )
    issues.extend(calibration_issues)
    issues.extend(cross_table_issues)
    issues.extend(statistical_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "output_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "require_statistical_report": bool(require_statistical_report),
        "required_fixed_fpr_outputs": list(REQUIRED_FIXED_FPR_OUTPUTS),
        "required_output_checks": required_checks,
        "table_read_errors": table_json_errors,
        "table_checks": table_checks,
        "table_summaries": table_summaries,
        "calibration_source_checks": calibration_checks,
        "cross_table_checks": cross_table_checks,
        "statistical_report_check": statistical_report_check,
        "blocking_issues": issues,
        "summary": {
            "missing_required_output_count": sum(1 for item in required_checks if not item["exists"]),
            "threshold_row_count": table_summaries[FIXED_FPR_THRESHOLD_TABLE_NAME]["row_count"],
            "tpr_row_count": table_summaries[TPR_AT_FIXED_FPR_TABLE_NAME]["row_count"],
            "attack_tpr_row_count": table_summaries[ATTACK_TPR_AT_FIXED_FPR_TABLE_NAME]["row_count"],
            "baseline_comparison_row_count": table_summaries[BASELINE_COMPARISON_TABLE_NAME]["row_count"],
            "method_count": len(table_summaries[TPR_AT_FIXED_FPR_TABLE_NAME]["method_names"]),
            "target_fpr_count": len(table_summaries[TPR_AT_FIXED_FPR_TABLE_NAME]["target_fprs"]),
            "statistical_report_exists": statistical_report_check["exists"],
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_fixed_fpr_output_acceptance_report(
    output_root: str | Path,
    out: str | Path,
    *,
    require_statistical_report: bool = False,
) -> dict[str, Any]:
    """写出 fixed-FPR / TPR@FPR 统计输出接收门禁报告。"""
    report = build_pilot_fixed_fpr_output_acceptance_report(output_root, require_statistical_report=require_statistical_report)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
