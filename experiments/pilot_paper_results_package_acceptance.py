"""校验 paper_results_package 是否可作为论文撰写和归档输入。

该模块位于 experiments 层, 用于接收 `export_paper_results_package.py` 或 MyDrive 归档流程已经
产出的结果包。它不重新计算论文指标, 只检查结果包 manifest、validation、核心 records、表格、
图表、报告和可选 evidence / image example 是否存在且可追溯。

通用工程写法是: 在交付或归档前检查 package manifest 与文件摘要一致。项目特定写法是: 明确
要求 CEG 论文主表相关 artifact、readiness、claim audit 和 evidence report 进入结果包, 避免把
手工拼接文件当作论文写作依据。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from main.analysis.result_package import PACKAGE_MANIFEST_NAME, validate_paper_results_package

REPORT_NAME = "pilot_paper_results_package_acceptance_report.json"
VALIDATION_REPORT_NAME = "paper_results_package_validation.json"
NEXT_STAGE_ON_PASS = "mydrive_archive_pilot"
NEXT_STAGE_ON_FAIL = "export_paper_results_package_and_fix_outputs"

REQUIRED_PACKAGE_FILES = (
    PACKAGE_MANIFEST_NAME,
    VALIDATION_REPORT_NAME,
    "event_records.json",
    "paper_outputs_summary.json",
    "paper_readiness_report.json",
    "paper_results_report.md",
    "paper_results_report_manifest.json",
    "paper_writing_index.json",
    "paper_writing_index.md",
    "artifacts/artifact_manifest.json",
    "artifacts/paper_claim_audit.json",
    "artifacts/fixed_fpr_threshold_table.csv",
    "artifacts/tpr_at_fixed_fpr_table.csv",
    "artifacts/attack_tpr_at_fixed_fpr_table.csv",
    "artifacts/baseline_comparison_table.csv",
    "latex_tables/latex_tables_manifest.json",
    "rendered_figures/rendered_paper_figures_manifest.json",
    "pdf_figures/paper_figures_pdf_manifest.json",
)
EVIDENCE_FILES = (
    "paper_result_evidence_report.json",
    "external_result_evidence_report.json",
)
IMAGE_EXAMPLE_FILES = (
    "image_examples/image_example_manifest.json",
)


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _required_file_checks(package_root: Path, required_files: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查结果包内必需文件是否存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in required_files:
        path = package_root / relative
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
            issues.append({"issue_type": "missing_required_package_file", "relative_path": relative})
    return checks, issues


def _manifest_checks(package_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """检查 paper_results_package_manifest.json 的基本一致性。"""
    path = package_root / PACKAGE_MANIFEST_NAME
    payload, error = _read_json(path) if path.is_file() else (None, "missing_package_manifest")
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    summary = {
        "package_status": None,
        "file_count": 0,
        "copied_file_count": 0,
        "readiness_decision": None,
        "claim_audit_decision": None,
    }
    if error is not None:
        issues.append({"issue_type": "unreadable_or_missing_package_manifest", "error": error})
        return checks, issues, summary
    if not isinstance(payload, dict):
        issues.append({"issue_type": "package_manifest_not_object"})
        return checks, issues, summary
    files = payload.get("files")
    copied_files = payload.get("copied_files")
    if not isinstance(files, list):
        files = []
        issues.append({"issue_type": "package_manifest_files_not_list"})
    if not isinstance(copied_files, list):
        copied_files = []
        issues.append({"issue_type": "package_manifest_copied_files_not_list"})
    summary = {
        "package_status": payload.get("package_status"),
        "file_count": payload.get("file_count") if isinstance(payload.get("file_count"), int) else 0,
        "copied_file_count": len(copied_files),
        "readiness_decision": payload.get("readiness_decision"),
        "claim_audit_decision": payload.get("claim_audit_decision"),
    }
    checks.extend(
        [
            {
                "check_name": "artifact_name_matches",
                "passes": payload.get("artifact_name") == PACKAGE_MANIFEST_NAME,
                "actual": payload.get("artifact_name"),
            },
            {
                "check_name": "package_status_complete",
                "passes": payload.get("package_status") == "complete",
                "actual": payload.get("package_status"),
            },
            {
                "check_name": "file_count_matches_files",
                "passes": payload.get("file_count") == len(files),
                "manifest_file_count": payload.get("file_count"),
                "actual_file_count": len(files),
            },
            {
                "check_name": "readiness_pass",
                "passes": payload.get("readiness_decision") == "pass",
                "actual": payload.get("readiness_decision"),
            },
            {
                "check_name": "claim_audit_pass",
                "passes": payload.get("claim_audit_decision") == "pass",
                "actual": payload.get("claim_audit_decision"),
            },
        ]
    )
    for check in checks:
        if not check["passes"]:
            issues.append({"issue_type": "package_manifest_check_failed", "check_name": check["check_name"], "actual": check.get("actual")})
    return checks, issues, summary


def _validation_checks(package_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """检查已有 validation report, 并重新运行 digest validation。"""
    report_path = package_root / VALIDATION_REPORT_NAME
    payload, error = _read_json(report_path) if report_path.is_file() else (None, "missing_package_validation_report")
    fresh_validation = validate_paper_results_package(package_root)
    checks = [
        {
            "check_name": "validation_report_exists_and_readable",
            "passes": error is None,
            "json_error": error,
        },
        {
            "check_name": "validation_report_pass",
            "passes": isinstance(payload, dict) and payload.get("overall_decision") == "pass",
            "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
        },
        {
            "check_name": "fresh_validation_pass",
            "passes": fresh_validation.get("overall_decision") == "pass",
            "overall_decision": fresh_validation.get("overall_decision"),
        },
    ]
    issues: list[dict[str, Any]] = []
    for check in checks:
        if not check["passes"]:
            issues.append({"issue_type": "package_validation_check_failed", "check_name": check["check_name"], "overall_decision": check.get("overall_decision"), "json_error": check.get("json_error")})
    return checks, issues, fresh_validation


def _evidence_checks(package_root: Path, *, require_evidence: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查结果包中的 evidence reports。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in EVIDENCE_FILES:
        path = package_root / relative
        payload, error = _read_json(path) if path.is_file() else (None, f"missing_{relative}")
        check = {
            "relative_path": relative,
            "exists": path.is_file(),
            "readable_json": error is None,
            "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
            "require_evidence": require_evidence,
        }
        checks.append(check)
        if require_evidence:
            if error is not None:
                issues.append({"issue_type": "missing_required_package_evidence", "relative_path": relative, "error": error})
            elif not isinstance(payload, dict) or payload.get("overall_decision") != "pass":
                issues.append({"issue_type": "package_evidence_not_pass", "relative_path": relative, "overall_decision": check["overall_decision"]})
    return checks, issues


def _image_example_checks(package_root: Path, *, require_image_examples: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """检查示例图 manifest 及其索引文件。"""
    checks, raw_issues = _required_file_checks(package_root, IMAGE_EXAMPLE_FILES)
    issues = raw_issues if require_image_examples else []
    manifest_path = package_root / IMAGE_EXAMPLE_FILES[0]
    payload, error = _read_json(manifest_path) if manifest_path.is_file() else (None, "missing_image_example_manifest")
    example_count = 0
    missing_examples: list[str] = []
    if isinstance(payload, dict):
        examples = payload.get("examples", [])
        if isinstance(examples, list):
            example_count = len(examples)
            for item in examples:
                if isinstance(item, dict) and item.get("relative_path") and not (package_root / str(item["relative_path"])).is_file():
                    missing_examples.append(str(item["relative_path"]))
    if require_image_examples:
        if error is not None:
            issues.append({"issue_type": "missing_required_image_example_manifest", "error": error})
        if example_count == 0:
            issues.append({"issue_type": "empty_image_example_manifest"})
        for relative in missing_examples:
            issues.append({"issue_type": "missing_image_example_file", "relative_path": relative})
    return checks, issues, {"example_count": example_count, "missing_example_files": missing_examples}


def build_pilot_paper_results_package_acceptance_report(
    package_root: str | Path,
    *,
    require_evidence: bool = False,
    require_image_examples: bool = False,
) -> dict[str, Any]:
    """构建 paper_results_package 输出接收门禁报告。"""
    root = Path(package_root)
    issues: list[dict[str, Any]] = []
    required_checks, required_issues = _required_file_checks(root, REQUIRED_PACKAGE_FILES)
    manifest_checks, manifest_issues, manifest_summary = _manifest_checks(root)
    validation_checks, validation_issues, fresh_validation = _validation_checks(root)
    evidence_checks, evidence_issues = _evidence_checks(root, require_evidence=require_evidence)
    image_checks, image_issues, image_summary = _image_example_checks(root, require_image_examples=require_image_examples)
    issues.extend(required_issues)
    issues.extend(manifest_issues)
    issues.extend(validation_issues)
    issues.extend(evidence_issues)
    issues.extend(image_issues)
    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "package_root": str(root),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "require_evidence": bool(require_evidence),
        "require_image_examples": bool(require_image_examples),
        "required_package_files": list(REQUIRED_PACKAGE_FILES),
        "required_file_checks": required_checks,
        "manifest_checks": manifest_checks,
        "validation_checks": validation_checks,
        "fresh_validation": fresh_validation,
        "evidence_checks": evidence_checks,
        "image_example_checks": image_checks,
        "manifest_summary": manifest_summary,
        "image_example_summary": image_summary,
        "blocking_issues": issues,
        "summary": {
            "missing_required_file_count": sum(1 for item in required_checks if not item["exists"]),
            "package_file_count": manifest_summary["file_count"],
            "copied_file_count": manifest_summary["copied_file_count"],
            "readiness_decision": manifest_summary["readiness_decision"],
            "claim_audit_decision": manifest_summary["claim_audit_decision"],
            "fresh_validation_decision": fresh_validation.get("overall_decision"),
            "evidence_file_count": sum(1 for item in evidence_checks if item["exists"]),
            "image_example_count": image_summary["example_count"],
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_paper_results_package_acceptance_report(
    package_root: str | Path,
    out: str | Path,
    *,
    require_evidence: bool = False,
    require_image_examples: bool = False,
) -> dict[str, Any]:
    """写出 paper_results_package 输出接收门禁报告。"""
    report = build_pilot_paper_results_package_acceptance_report(
        package_root,
        require_evidence=require_evidence,
        require_image_examples=require_image_examples,
    )
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
