"""校验论文结果输出目录是否覆盖正式论文所需产物。

该模块属于产物审计层, 只检查已经生成的 records、tables、figures、PDF 和 manifest。
它不改变 CEG 判定算法, 也不替代真实实验; 它的作用是把“是否已经足以支撑论文结果”变成可执行检查。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from main.analysis.latex_tables import DEFAULT_LATEX_TABLES
from main.analysis.rebuild_artifacts import (
    PW02_ARTIFACT_NAMES,
    PW04_ARTIFACT_NAMES,
    PW05_STANDARD_METRIC_ARTIFACT_NAMES,
    PW06_FIGURE_ARTIFACT_NAMES,
    PW07_UNCERTAINTY_ARTIFACT_NAMES,
    PW08_DETECTION_CURVE_ARTIFACT_NAMES,
    PW09_CLAIM_AUDIT_ARTIFACT_NAMES,
    PW10_FIXED_FPR_ARTIFACT_NAMES,
)

DEFAULT_REQUIRED_ARTIFACTS = tuple(
    list(PW02_ARTIFACT_NAMES)
    + list(PW04_ARTIFACT_NAMES)
    + list(PW05_STANDARD_METRIC_ARTIFACT_NAMES)
    + list(PW06_FIGURE_ARTIFACT_NAMES)
    + list(PW07_UNCERTAINTY_ARTIFACT_NAMES)
    + list(PW08_DETECTION_CURVE_ARTIFACT_NAMES)
    + list(PW09_CLAIM_AUDIT_ARTIFACT_NAMES)
    + list(PW10_FIXED_FPR_ARTIFACT_NAMES)
)
DEFAULT_REQUIRED_FIGURE_IDS = (
    "main_detection_comparison",
    "rescue_ablation_contribution",
    "quality_detection_tradeoff",
    "attack_family_robustness",
    "detection_roc_curves",
    "score_distribution_by_method",
    "detection_confidence_intervals",
    "bit_recovery_comparison",
)
DEFAULT_REQUIRED_METHODS = (
    "ceg",
    "ceg_full",
    "ceg_content_only",
    "ceg_recover_then_content",
    "ceg_no_rescue",
    "ceg_no_attestation",
    "tree_ring",
    "gaussian_shading",
    "shallow_diffuse",
    "stable_signature_dee",
)
DEFAULT_REQUIRED_SAMPLE_ROLES = ("positive_source", "clean_negative", "attacked_negative")
DEFAULT_REQUIRED_TABLE_COLUMNS = {
    "formal_main_table.csv": ("method_name", "tpr", "clean_fpr", "attacked_negative_fpr"),
    "rescue_metrics_summary.csv": ("method_name", "rescue_gain", "positive_by_geo_rescue_count"),
    "baseline_comparison_table.csv": ("method_name", "event_count", "tpr", "clean_fpr"),
    "method_group_comparison_table.csv": ("method_name", "method_group", "comparison_role", "event_count", "tpr", "clean_fpr"),
    "quality_metrics_summary.csv": ("method_name", "metric_name", "metric_mean", "metric_coverage_rate"),
    "bit_recovery_metrics.csv": ("method_name", "bit_accuracy", "payload_recovery_rate"),
    "attack_family_metrics.csv": ("method_name", "attack_family", "tpr", "bit_accuracy"),
    "rate_confidence_intervals.csv": ("method_name", "metric_name", "rate_value", "ci_lower", "ci_upper"),
    "method_pairwise_delta_table.csv": ("reference_method", "method_name", "metric_name", "rate_delta"),
    "detection_roc_curve.csv": ("method_name", "threshold_label", "tpr", "fpr"),
    "score_histogram_table.csv": ("method_name", "label_name", "score_bin_lower", "score_bin_count"),
    "operating_point_table.csv": ("method_name", "operating_threshold", "tpr", "fpr"),
    "fixed_fpr_threshold_table.csv": ("method_name", "target_fpr", "threshold_value", "calibration_negative_count", "calibration_observed_fpr"),
    "tpr_at_fixed_fpr_table.csv": ("method_name", "target_fpr", "threshold_value", "test_fpr_at_threshold", "tpr_at_fixed_fpr"),
    "attack_tpr_at_fixed_fpr_table.csv": ("method_name", "target_fpr", "attack_family", "attack_tpr_at_fixed_fpr"),
}


def load_paper_output_requirements(path: str | Path) -> dict[str, Any]:
    """读取论文输出完整性需求配置。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("paper output requirements must contain an object")
    return dict(payload)


def default_paper_output_requirements() -> dict[str, Any]:
    """返回内置论文结果输出需求。"""
    return {
        "required_artifacts": list(DEFAULT_REQUIRED_ARTIFACTS),
        "required_figure_ids": list(DEFAULT_REQUIRED_FIGURE_IDS),
        "required_latex_tables": [name.replace(".csv", ".tex") for name in DEFAULT_LATEX_TABLES],
        "required_methods": list(DEFAULT_REQUIRED_METHODS),
        "required_sample_roles": list(DEFAULT_REQUIRED_SAMPLE_ROLES),
        "required_table_columns": {key: list(value) for key, value in DEFAULT_REQUIRED_TABLE_COLUMNS.items()},
        "minimum_record_count": 1,
        "minimum_figure_count": len(DEFAULT_REQUIRED_FIGURE_IDS),
        "minimum_latex_table_count": len(DEFAULT_LATEX_TABLES),
    }


def _requirements(overrides: dict[str, Any] | None) -> dict[str, Any]:
    """合并默认需求和调用方覆盖项。"""
    base = default_paper_output_requirements()
    if overrides:
        for key, value in overrides.items():
            base[key] = value
    return base


def _pass(name: str, evidence: Any) -> dict[str, Any]:
    """构造通过检查项。"""
    return {"requirement": name, "status": "pass", "evidence": evidence}


def _fail(name: str, evidence: Any) -> dict[str, Any]:
    """构造失败检查项。"""
    return {"requirement": name, "status": "fail", "evidence": evidence}


def _read_json(path: Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """读取 CSV 行。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _check_event_records(output_root: Path, requirements: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """检查 event_records.json 是否存在并覆盖方法和样本角色。"""
    path = output_root / "event_records.json"
    if not path.exists():
        return _fail("event_records_exist", {"missing": "event_records.json"}), []
    records = _read_json(path)
    if not isinstance(records, list):
        return _fail("event_records_exist", {"reason": "event_records_not_list"}), []
    minimum = int(requirements.get("minimum_record_count", 1))
    if len(records) < minimum:
        return _fail("event_records_exist", {"record_count": len(records), "minimum_record_count": minimum}), []
    return _pass("event_records_exist", {"record_count": len(records)}), [dict(row) for row in records if isinstance(row, dict)]


def _check_required_methods(records: list[dict[str, Any]], requirements: dict[str, Any]) -> dict[str, Any]:
    """检查 records 是否包含论文主方法、内部消融和外部 baseline。"""
    present = {str(row.get("method_name")) for row in records}
    required = set(str(item) for item in requirements.get("required_methods", []))
    missing = sorted(required - present)
    if missing:
        return _fail("required_methods_present", {"missing": missing, "present": sorted(present)})
    return _pass("required_methods_present", sorted(required))


def _check_required_sample_roles(records: list[dict[str, Any]], requirements: dict[str, Any]) -> dict[str, Any]:
    """检查 records 是否覆盖正例、clean 负例和攻击负例。"""
    present = {str(row.get("sample_role")) for row in records}
    required = set(str(item) for item in requirements.get("required_sample_roles", []))
    missing = sorted(required - present)
    if missing:
        return _fail("required_sample_roles_present", {"missing": missing, "present": sorted(present)})
    return _pass("required_sample_roles_present", sorted(required))


def _check_artifact_bundle(output_root: Path, requirements: dict[str, Any]) -> dict[str, Any]:
    """检查 artifacts 目录中的核心 JSON / CSV 产物。"""
    artifact_root = output_root / "artifacts"
    manifest_path = artifact_root / "artifact_manifest.json"
    if not manifest_path.exists():
        return _fail("required_artifacts_present", {"missing": "artifacts/artifact_manifest.json"})
    manifest = _read_json(manifest_path)
    artifact_names = set(str(item) for item in manifest.get("artifact_names", [])) if isinstance(manifest, dict) else set()
    required = set(str(item) for item in requirements.get("required_artifacts", []))
    missing_manifest = sorted(required - artifact_names)
    missing_files = sorted(name for name in required if not (artifact_root / name).exists())
    empty_files = sorted(name for name in required if (artifact_root / name).exists() and (artifact_root / name).stat().st_size == 0)
    if missing_manifest or missing_files or empty_files:
        return _fail(
            "required_artifacts_present",
            {"missing_manifest_entries": missing_manifest, "missing_files": missing_files, "empty_files": empty_files},
        )
    return _pass("required_artifacts_present", sorted(required))


def _check_table_columns(output_root: Path, requirements: dict[str, Any]) -> dict[str, Any]:
    """检查关键 CSV 表格是否包含论文图表所需列且至少有一行数据。"""
    artifact_root = output_root / "artifacts"
    violations: list[dict[str, Any]] = []
    table_columns = requirements.get("required_table_columns", {})
    if not isinstance(table_columns, dict):
        return _fail("required_table_columns_present", {"reason": "required_table_columns_not_object"})
    for table_name, columns in sorted(table_columns.items()):
        table_path = artifact_root / str(table_name)
        if not table_path.exists():
            violations.append({"table_name": table_name, "reason": "missing_table"})
            continue
        rows = _read_csv_rows(table_path)
        present_columns = set(rows[0]) if rows else set()
        if not rows:
            violations.append({"table_name": table_name, "reason": "table_has_no_rows"})
        missing_columns = sorted(set(str(column) for column in columns) - present_columns)
        if missing_columns:
            violations.append({"table_name": table_name, "reason": "missing_columns", "missing_columns": missing_columns})
    if violations:
        return _fail("required_table_columns_present", violations)
    return _pass("required_table_columns_present", sorted(table_columns))


def _check_figure_specs(output_root: Path, requirements: dict[str, Any]) -> dict[str, Any]:
    """检查 paper_figure_specs.json 是否覆盖所有论文核心图。"""
    path = output_root / "artifacts" / "paper_figure_specs.json"
    if not path.exists():
        return _fail("required_figure_specs_present", {"missing": "artifacts/paper_figure_specs.json"})
    specs = _read_json(path)
    figures = specs.get("figures", []) if isinstance(specs, dict) else []
    figure_ids = {str(figure.get("figure_id")) for figure in figures if isinstance(figure, dict)}
    required = set(str(item) for item in requirements.get("required_figure_ids", []))
    minimum = int(requirements.get("minimum_figure_count", len(required)))
    missing = sorted(required - figure_ids)
    if missing or len(figures) < minimum:
        return _fail(
            "required_figure_specs_present",
            {"missing": missing, "figure_count": len(figures), "minimum_figure_count": minimum},
        )
    return _pass("required_figure_specs_present", {"figure_count": len(figures), "figure_ids": sorted(figure_ids)})


def _check_rendered_figures(output_root: Path) -> dict[str, Any]:
    """检查 SVG 和 HTML 图表渲染产物是否存在。"""
    rendered_root = output_root / "rendered_figures"
    manifest_path = rendered_root / "rendered_paper_figures_manifest.json"
    if not manifest_path.exists():
        return _fail("rendered_figure_outputs_present", {"missing": "rendered_figures/rendered_paper_figures_manifest.json"})
    manifest = _read_json(manifest_path)
    rendered = manifest.get("rendered_figures", []) if isinstance(manifest, dict) else []
    missing = []
    for item in rendered:
        if isinstance(item, dict):
            relative = str(item.get("svg_path"))
            if not (rendered_root / relative).exists():
                missing.append(relative)
    report_path = rendered_root / str(manifest.get("report_path", "paper_figures_report.html"))
    if missing or not report_path.exists():
        return _fail("rendered_figure_outputs_present", {"missing_svg": missing, "html_exists": report_path.exists()})
    return _pass("rendered_figure_outputs_present", {"figure_count": len(rendered), "report_path": str(report_path.name)})


def _check_latex_tables(output_root: Path, requirements: dict[str, Any]) -> dict[str, Any]:
    """检查 LaTeX 表格导出是否完整。"""
    latex_root = output_root / "latex_tables"
    manifest_path = latex_root / "latex_tables_manifest.json"
    if not manifest_path.exists():
        return _fail("latex_table_outputs_present", {"missing": "latex_tables/latex_tables_manifest.json"})
    manifest = _read_json(manifest_path)
    tables = set(str(item) for item in manifest.get("latex_tables", [])) if isinstance(manifest, dict) else set()
    required = set(str(item) for item in requirements.get("required_latex_tables", []))
    missing = sorted(name for name in required if name not in tables or not (latex_root / name).exists())
    minimum = int(requirements.get("minimum_latex_table_count", len(required)))
    if missing or len(tables) < minimum:
        return _fail("latex_table_outputs_present", {"missing": missing, "table_count": len(tables), "minimum": minimum})
    return _pass("latex_table_outputs_present", {"table_count": len(tables), "latex_tables": sorted(tables)})


def _check_pdf_figures(output_root: Path) -> dict[str, Any]:
    """检查 PDF 图表预览是否可识别。"""
    pdf_root = output_root / "pdf_figures"
    manifest_path = pdf_root / "paper_figures_pdf_manifest.json"
    if not manifest_path.exists():
        return _fail("pdf_figure_outputs_present", {"missing": "pdf_figures/paper_figures_pdf_manifest.json"})
    manifest = _read_json(manifest_path)
    pdf_path = pdf_root / str(manifest.get("pdf_path", "paper_figures_preview.pdf"))
    if not pdf_path.exists() or not pdf_path.read_bytes().startswith(b"%PDF"):
        return _fail("pdf_figure_outputs_present", {"pdf_path": str(pdf_path), "reason": "missing_or_invalid_pdf"})
    return _pass("pdf_figure_outputs_present", {"pdf_path": pdf_path.name, "page_count": manifest.get("page_count")})



def _check_markdown_report(output_root: Path) -> dict[str, Any]:
    """检查 Markdown 论文结果报告和 manifest 是否存在。"""
    report_path = output_root / "paper_results_report.md"
    manifest_path = output_root / "paper_results_report_manifest.json"
    missing = []
    if not report_path.exists() or report_path.stat().st_size == 0:
        missing.append("paper_results_report.md")
    if not manifest_path.exists() or manifest_path.stat().st_size == 0:
        missing.append("paper_results_report_manifest.json")
    if missing:
        return _fail("paper_results_report_present", {"missing": missing})
    manifest = _read_json(manifest_path)
    return _pass(
        "paper_results_report_present",
        {"report_path": report_path.name, "manifest_artifact": manifest.get("artifact_name")},
    )


def _check_claim_audit(output_root: Path) -> dict[str, Any]:
    """检查论文 supported claims 是否全部绑定到受治理产物。"""
    path = output_root / "artifacts" / "paper_claim_audit.json"
    if not path.exists():
        return _fail("paper_claim_audit_passed", {"missing": "artifacts/paper_claim_audit.json"})
    payload = _read_json(path)
    claims = payload.get("claims", []) if isinstance(payload, dict) else []
    failed = [claim for claim in claims if isinstance(claim, dict) and claim.get("status") != "pass"]
    if not isinstance(payload, dict) or payload.get("overall_decision") != "pass" or failed:
        return _fail(
            "paper_claim_audit_passed",
            {
                "overall_decision": payload.get("overall_decision") if isinstance(payload, dict) else None,
                "failed_claim_ids": [str(claim.get("claim_id")) for claim in failed],
            },
        )
    return _pass(
        "paper_claim_audit_passed",
        {"claim_count": payload.get("claim_count"), "supported_claim_count": payload.get("supported_claim_count")},
    )

def _check_summary(output_root: Path) -> dict[str, Any]:
    """检查一键输出摘要是否指向核心 manifest。"""
    path = output_root / "paper_outputs_summary.json"
    if not path.exists():
        return _fail("paper_outputs_summary_present", {"missing": "paper_outputs_summary.json"})
    summary = _read_json(path)
    required_keys = {
        "artifact_manifest_path",
        "rendered_figures_manifest_path",
        "latex_tables_manifest_path",
        "pdf_figures_manifest_path",
        "paper_results_report_path",
        "paper_results_report_manifest_path",
    }
    missing = sorted(key for key in required_keys if key not in summary)
    if missing:
        return _fail("paper_outputs_summary_present", {"missing_keys": missing})
    return _pass("paper_outputs_summary_present", {key: summary[key] for key in sorted(required_keys)})


def validate_paper_output_directory(
    output_root: str | Path,
    *,
    requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """校验一键论文输出目录并返回 readiness 报告。"""
    root = Path(output_root)
    merged_requirements = _requirements(requirements)
    record_check, records = _check_event_records(root, merged_requirements)
    checks = [
        record_check,
        _check_required_methods(records, merged_requirements),
        _check_required_sample_roles(records, merged_requirements),
        _check_artifact_bundle(root, merged_requirements),
        _check_table_columns(root, merged_requirements),
        _check_figure_specs(root, merged_requirements),
        _check_rendered_figures(root),
        _check_latex_tables(root, merged_requirements),
        _check_pdf_figures(root),
        _check_markdown_report(root),
        _check_claim_audit(root),
        _check_summary(root),
    ]
    fail_count = sum(1 for item in checks if item["status"] != "pass")
    return {
        "artifact_name": "paper_readiness_report.json",
        "overall_decision": "fail" if fail_count else "pass",
        "checks": checks,
        "summary": {"total": len(checks), "fail_count": fail_count, "pass_count": len(checks) - fail_count},
    }


def write_paper_readiness_report(
    output_root: str | Path,
    *,
    requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写出 paper_readiness_report.json。"""
    root = Path(output_root)
    report = validate_paper_output_directory(root, requirements=requirements)
    (root / "paper_readiness_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
