"""从论文 CSV 表格产物生成 LaTeX table。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_LATEX_TABLES = (
    "formal_main_table.csv",
    "rescue_metrics_summary.csv",
    "baseline_comparison_table.csv",
    "method_group_comparison_table.csv",
    "quality_metrics_summary.csv",
    "bit_recovery_metrics.csv",
    "attack_family_metrics.csv",
    "rate_confidence_intervals.csv",
    "method_pairwise_delta_table.csv",
    "detection_roc_curve.csv",
    "score_histogram_table.csv",
    "operating_point_table.csv",
    "fixed_fpr_threshold_table.csv",
    "tpr_at_fixed_fpr_table.csv",
    "attack_tpr_at_fixed_fpr_table.csv",
)


def _escape_latex(value: Any) -> str:
    """转义 LaTeX 表格中的特殊字符。"""
    if value is None:
        return "--"
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _format_value(value: Any) -> str:
    """格式化表格单元格, 让浮点数适合论文草稿审阅。"""
    if isinstance(value, float):
        return f"{value:.4g}"
    return _escape_latex(value)


def build_latex_table(table_name: str, rows: list[dict[str, Any]], *, caption: str | None = None) -> str:
    """把内存中的表格行转换为 LaTeX tabular。"""
    fieldnames = sorted({key for row in rows for key in row})
    if not fieldnames:
        fieldnames = ["empty"]
        rows = [{"empty": "no rows"}]
    column_spec = "l" * len(fieldnames)
    label = table_name.replace(".csv", "").replace("_", "-")
    header = " & ".join(_escape_latex(field) for field in fieldnames)
    body_lines = [" & ".join(_format_value(row.get(field)) for field in fieldnames) + r" \\" for row in rows]
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            rf"\caption{{{_escape_latex(caption or table_name)}}}",
            rf"\label{{tab:{_escape_latex(label)}}}",
            rf"\begin{{tabular}}{{{column_spec}}}",
            r"\hline",
            header + r" \\ ",
            r"\hline",
            *body_lines,
            r"\hline",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )


def build_latex_tables_from_artifacts(artifacts: dict[str, Any]) -> dict[str, str]:
    """从 artifact 字典中抽取 CSV 表格并生成 LaTeX 文本。"""
    latex_tables: dict[str, str] = {}
    for artifact_name in DEFAULT_LATEX_TABLES:
        payload = artifacts.get(artifact_name)
        if isinstance(payload, list):
            latex_tables[artifact_name.replace(".csv", ".tex")] = build_latex_table(artifact_name, payload)
    return latex_tables


def write_latex_tables(output_root: str | Path, artifacts: dict[str, Any]) -> dict[str, Any]:
    """写出 LaTeX 表格文件和 manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    latex_tables = build_latex_tables_from_artifacts(artifacts)
    written = []
    for file_name, latex_text in latex_tables.items():
        (output_path / file_name).write_text(latex_text, encoding="utf-8")
        written.append(file_name)
    manifest = {
        "artifact_name": "latex_tables_manifest.json",
        "table_count": len(written),
        "latex_tables": sorted(written),
    }
    (output_path / "latex_tables_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_latex_tables_from_csv_dir(input_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    """从已经写出的 CSV 目录读取表格并生成 LaTeX 文件。"""
    input_path = Path(input_root)
    artifacts: dict[str, Any] = {}
    for table_name in DEFAULT_LATEX_TABLES:
        table_path = input_path / table_name
        if not table_path.exists():
            continue
        with table_path.open("r", encoding="utf-8-sig", newline="") as handle:
            artifacts[table_name] = [dict(row) for row in csv.DictReader(handle)]
    return write_latex_tables(output_root, artifacts)
