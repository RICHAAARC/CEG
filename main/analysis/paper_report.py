"""从论文输出目录生成可审计的 Markdown 结果报告。

该模块把已经重建出的 records、artifacts、figures、LaTeX、PDF 和 readiness 报告组织为人类可读的结果摘要。
它不重新计算方法结论, 只引用受治理产物, 避免论文报告与 records 脱节。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

CORE_RESULT_TABLES = (
    "formal_main_table.csv",
    "baseline_comparison_table.csv",
    "rescue_metrics_summary.csv",
    "quality_metrics_summary.csv",
    "bit_recovery_metrics.csv",
    "attack_family_metrics.csv",
    "rate_confidence_intervals.csv",
    "method_pairwise_delta_table.csv",
    "detection_roc_curve.csv",
    "score_histogram_table.csv",
    "operating_point_table.csv",
)


def _read_json_if_exists(path: Path) -> Any:
    """读取 JSON 文件, 缺失时返回 None。"""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv_rows(path: Path, *, limit: int = 6) -> list[dict[str, str]]:
    """读取 CSV 前若干行, 用于报告预览。"""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for index, row in enumerate(csv.DictReader(handle)):
            if index >= limit:
                break
            rows.append(dict(row))
        return rows


def _markdown_table(rows: list[dict[str, Any]], *, max_columns: int = 8) -> str:
    """把少量字典行渲染为 Markdown 表格。"""
    if not rows:
        return "无可预览行。\n"
    columns = list(rows[0])[:max_columns]
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join([header, divider, *body]) + "\n"


def _status_counts(readiness_report: dict[str, Any] | None) -> dict[str, int]:
    """统计 readiness 检查状态。"""
    counts: dict[str, int] = {}
    if not isinstance(readiness_report, dict):
        return counts
    for item in readiness_report.get("checks", []):
        if isinstance(item, dict):
            status = str(item.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
    return counts


def _method_coverage(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按方法统计 record 数和样本角色覆盖。"""
    grouped: dict[str, dict[str, Any]] = {}
    for row in records:
        method_name = str(row.get("method_name") or "unknown_method")
        item = grouped.setdefault(method_name, {"method_name": method_name, "record_count": 0, "sample_roles": set()})
        item["record_count"] += 1
        item["sample_roles"].add(str(row.get("sample_role") or "unknown_role"))
    output = []
    for item in grouped.values():
        output.append(
            {
                "method_name": item["method_name"],
                "record_count": item["record_count"],
                "sample_roles": ",".join(sorted(item["sample_roles"])),
            }
        )
    return sorted(output, key=lambda row: row["method_name"])


def build_paper_results_report(output_root: str | Path) -> tuple[str, dict[str, Any]]:
    """从一键输出目录构建 Markdown 报告文本和 manifest。"""
    root = Path(output_root)
    summary = _read_json_if_exists(root / "paper_outputs_summary.json") or {}
    records = _read_json_if_exists(root / "event_records.json") or []
    artifact_manifest = _read_json_if_exists(root / "artifacts" / "artifact_manifest.json") or {}
    figure_specs = _read_json_if_exists(root / "artifacts" / "paper_figure_specs.json") or {}
    rendered_manifest = _read_json_if_exists(root / "rendered_figures" / "rendered_paper_figures_manifest.json") or {}
    latex_manifest = _read_json_if_exists(root / "latex_tables" / "latex_tables_manifest.json") or {}
    pdf_manifest = _read_json_if_exists(root / "pdf_figures" / "paper_figures_pdf_manifest.json") or {}
    readiness_report = _read_json_if_exists(root / "paper_readiness_report.json") or {}
    claim_audit = _read_json_if_exists(root / "artifacts" / "paper_claim_audit.json") or {}
    coverage_report = _read_json_if_exists(root / "artifacts" / "paper_experiment_coverage_report.json") or {}

    artifact_names = artifact_manifest.get("artifact_names", []) if isinstance(artifact_manifest, dict) else []
    figures = figure_specs.get("figures", []) if isinstance(figure_specs, dict) else []
    readiness_counts = _status_counts(readiness_report)
    method_rows = _method_coverage([dict(row) for row in records if isinstance(row, dict)]) if isinstance(records, list) else []

    lines = [
        "# CEG 论文结果包报告",
        "",
        "## 1. 输出包摘要",
        "",
        f"- profile: `{summary.get('profile', 'unknown')}`",
        f"- record_count: `{summary.get('record_count', len(records) if isinstance(records, list) else 0)}`",
        f"- artifact_count: `{summary.get('artifact_count', len(artifact_names))}`",
        f"- figure_count: `{summary.get('figure_count', len(figures))}`",
        f"- latex_table_count: `{summary.get('latex_table_count', len(latex_manifest.get('latex_tables', [])) if isinstance(latex_manifest, dict) else 0)}`",
        f"- paper_readiness_decision: `{summary.get('paper_readiness_decision', readiness_report.get('overall_decision', 'unknown') if isinstance(readiness_report, dict) else 'unknown')}`",
        f"- experiment_coverage_decision: `{summary.get('experiment_coverage_decision', coverage_report.get('overall_decision', 'not_available') if isinstance(coverage_report, dict) else 'not_available')}`",
        "",
        "## 2. 方法与样本角色覆盖",
        "",
        _markdown_table(method_rows),
        "## 3. 论文核心产物清单",
        "",
    ]
    for artifact_name in sorted(str(name) for name in artifact_names):
        lines.append(f"- `artifacts/{artifact_name}`")
    lines.extend(["", "## 4. 核心表格预览", ""])
    for table_name in CORE_RESULT_TABLES:
        table_path = root / "artifacts" / table_name
        lines.extend([f"### {table_name}", "", _markdown_table(_read_csv_rows(table_path)), ""])
    lines.extend(["## 5. 图表与导出文件", ""])
    for figure in figures:
        if not isinstance(figure, dict):
            continue
        lines.append(
            f"- `{figure.get('figure_id')}`: {figure.get('title')} | chart_type=`{figure.get('chart_type')}`"
        )
    if isinstance(rendered_manifest, dict):
        lines.append(f"- HTML 图表报告: `rendered_figures/{rendered_manifest.get('report_path', 'paper_figures_report.html')}`")
    if isinstance(pdf_manifest, dict):
        lines.append(f"- PDF 图表预览: `pdf_figures/{pdf_manifest.get('pdf_path', 'paper_figures_preview.pdf')}`")
    lines.extend(["", "## 6. Supported claims 审计", ""])
    if isinstance(claim_audit, dict):
        lines.append(f"- overall_decision: `{claim_audit.get('overall_decision', 'unknown')}`")
        lines.append(f"- supported_claim_count: `{claim_audit.get('supported_claim_count', 0)}` / `{claim_audit.get('claim_count', 0)}`")
        claim_rows = [
            {
                "claim_id": claim.get("claim_id"),
                "status": claim.get("status"),
                "supporting_artifacts": ",".join(str(item) for item in claim.get("supporting_artifacts", [])),
            }
            for claim in claim_audit.get("claims", [])
            if isinstance(claim, dict)
        ]
        lines.append(_markdown_table(claim_rows, max_columns=3))
    lines.extend(["", "## 7. 实验矩阵覆盖率审计", ""])
    if isinstance(coverage_report, dict) and coverage_report:
        lines.append(f"- overall_decision: `{coverage_report.get('overall_decision', 'unknown')}`")
        lines.append(f"- coverage_rate: `{coverage_report.get('coverage_rate', 'unknown')}`")
        lines.append(f"- missing_key_count: `{coverage_report.get('missing_key_count', 'unknown')}`")
        lines.append(_markdown_table([dict(row) for row in coverage_report.get('method_group_coverage', []) if isinstance(row, dict)]))
    else:
        lines.append("- coverage_report: `not_available`")

    lines.extend(["", "## 8. Readiness 检查摘要", ""])
    lines.append(_markdown_table([{"status": key, "count": value} for key, value in sorted(readiness_counts.items())]))
    if isinstance(readiness_report, dict):
        lines.append(f"- overall_decision: `{readiness_report.get('overall_decision', 'unknown')}`")
        for item in readiness_report.get("checks", []):
            if isinstance(item, dict):
                lines.append(f"- `{item.get('requirement')}`: `{item.get('status')}`")
    lines.extend([
        "",
        "## 9. 使用说明",
        "",
        "本报告只汇总受治理产物, 不手工改写正式结果。若需要更新数值, 应重新运行 `scripts/build_paper_outputs.py` 或 `scripts/run_paper_readiness_dry_run.py`。",
        "",
    ])
    manifest = {
        "artifact_name": "paper_results_report_manifest.json",
        "report_path": "paper_results_report.md",
        "record_count": len(records) if isinstance(records, list) else 0,
        "artifact_count": len(artifact_names),
        "figure_count": len(figures),
        "readiness_decision": readiness_report.get("overall_decision") if isinstance(readiness_report, dict) else None,
        "source_paths": [
            "event_records.json",
            "paper_outputs_summary.json",
            "artifacts/artifact_manifest.json",
            "artifacts/paper_figure_specs.json",
            "artifacts/paper_claim_audit.json",
            "artifacts/paper_experiment_coverage_report.json",
            "paper_readiness_report.json",
        ],
    }
    return "\n".join(lines), manifest


def write_paper_results_report(output_root: str | Path) -> dict[str, Any]:
    """写出 Markdown 报告和报告 manifest。"""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    report, manifest = build_paper_results_report(root)
    (root / "paper_results_report.md").write_text(report, encoding="utf-8")
    (root / "paper_results_report_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
