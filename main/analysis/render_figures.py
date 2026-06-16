"""把论文图表规格渲染为轻量 SVG 和 HTML 报告。

该模块刻意使用标准库实现基础图表, 目的是保证在最小复现环境中也能产出可审计图表文件。
更精细的 Matplotlib、Vega-Lite 或网页图表可以在保持 figure spec 不变的前提下替换渲染器。
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


SVG_WIDTH = 960
SVG_HEIGHT = 540
PADDING_LEFT = 120
PADDING_RIGHT = 40
PADDING_TOP = 70
PADDING_BOTTOM = 90
PALETTE = ("#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#4b5563")


def _number(value: Any) -> float | None:
    """读取可绘图数值, 缺失或非数值时返回 None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _escape(value: Any) -> str:
    """转义 SVG / HTML 文本。"""
    return html.escape(str(value), quote=True)


def _scale(value: float, minimum: float, maximum: float, start: float, end: float) -> float:
    """线性缩放数值, 最大值和最小值相等时返回中点。"""
    if maximum == minimum:
        return (start + end) / 2
    return start + (value - minimum) * (end - start) / (maximum - minimum)


def _svg_shell(title: str, body: str) -> str:
    """包裹 SVG 基础结构和标题。"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="{_escape(title)}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{PADDING_LEFT}" y="36" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{_escape(title)}</text>
{body}
</svg>
"""


def _render_bar_like(figure: dict[str, Any]) -> str:
    """渲染 bar / grouped_bar / heatmap 的简化 SVG。"""
    data = [row for row in figure.get("data", []) if isinstance(row, dict)]
    encodings = figure.get("encodings", {}) if isinstance(figure.get("encodings"), dict) else {}
    x_field = str(encodings.get("x", "method_name"))
    y_field = str(encodings.get("y", "metric_value"))
    color_field = encodings.get("color")
    drawable = [(str(row.get(x_field, "unknown")), _number(row.get(y_field)), row) for row in data]
    drawable = [(label, value, row) for label, value, row in drawable if value is not None]
    if not drawable:
        return _svg_shell(str(figure.get("title", "figure")), _empty_message("没有可绘制的数值数据"))
    max_value = max(max(value for _, value, _ in drawable), 0.0)
    min_value = min(min(value for _, value, _ in drawable), 0.0)
    plot_width = SVG_WIDTH - PADDING_LEFT - PADDING_RIGHT
    plot_height = SVG_HEIGHT - PADDING_TOP - PADDING_BOTTOM
    bar_gap = 8
    bar_width = max(8, (plot_width - bar_gap * (len(drawable) - 1)) / len(drawable))
    color_values = sorted({str(row.get(color_field, "series")) for _, _, row in drawable}) if color_field else ["series"]
    color_map = {value: PALETTE[index % len(PALETTE)] for index, value in enumerate(color_values)}
    parts = [_axes(min_value, max_value)]
    for index, (label, value, row) in enumerate(drawable):
        x = PADDING_LEFT + index * (bar_width + bar_gap)
        y_zero = _scale(0.0, min_value, max_value, PADDING_TOP + plot_height, PADDING_TOP)
        y_value = _scale(value, min_value, max_value, PADDING_TOP + plot_height, PADDING_TOP)
        rect_y = min(y_zero, y_value)
        rect_height = abs(y_zero - y_value)
        series = str(row.get(color_field, "series")) if color_field else "series"
        parts.append(f'  <rect x="{x:.2f}" y="{rect_y:.2f}" width="{bar_width:.2f}" height="{rect_height:.2f}" fill="{color_map[series]}" opacity="0.86"/>')
        parts.append(f'  <text x="{x + bar_width / 2:.2f}" y="{SVG_HEIGHT - 54}" font-family="Arial, sans-serif" font-size="11" fill="#374151" text-anchor="end" transform="rotate(-35 {x + bar_width / 2:.2f} {SVG_HEIGHT - 54})">{_escape(label)}</text>')
    parts.extend(_legend(color_map))
    return _svg_shell(str(figure.get("title", "figure")), "\n".join(parts))


def _render_scatter(figure: dict[str, Any]) -> str:
    """渲染 scatter / small multiples 的基础 SVG。"""
    data = [row for row in figure.get("data", []) if isinstance(row, dict)]
    encodings = figure.get("encodings", {}) if isinstance(figure.get("encodings"), dict) else {}
    x_field = str(encodings.get("x", "x"))
    y_field = str(encodings.get("y", "y"))
    color_field = str(encodings.get("color", "method_name"))
    drawable = [(row, _number(row.get(x_field)), _number(row.get(y_field))) for row in data]
    drawable = [(row, x, y) for row, x, y in drawable if x is not None and y is not None]
    if not drawable:
        return _svg_shell(str(figure.get("title", "figure")), _empty_message("没有可绘制的 x/y 数值数据"))
    x_values = [x for _, x, _ in drawable]
    y_values = [y for _, _, y in drawable]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    plot_width = SVG_WIDTH - PADDING_LEFT - PADDING_RIGHT
    plot_height = SVG_HEIGHT - PADDING_TOP - PADDING_BOTTOM
    color_values = sorted({str(row.get(color_field, "series")) for row, _, _ in drawable})
    color_map = {value: PALETTE[index % len(PALETTE)] for index, value in enumerate(color_values)}
    parts = [_axes(y_min, y_max)]
    parts.append(f'  <text x="{PADDING_LEFT + plot_width / 2}" y="{SVG_HEIGHT - 18}" font-family="Arial, sans-serif" font-size="12" fill="#374151" text-anchor="middle">{_escape(x_field)}</text>')
    parts.append(f'  <text x="30" y="{PADDING_TOP + plot_height / 2}" font-family="Arial, sans-serif" font-size="12" fill="#374151" text-anchor="middle" transform="rotate(-90 30 {PADDING_TOP + plot_height / 2})">{_escape(y_field)}</text>')
    for row, x_value, y_value in drawable:
        x = _scale(x_value, x_min, x_max, PADDING_LEFT, PADDING_LEFT + plot_width)
        y = _scale(y_value, y_min, y_max, PADDING_TOP + plot_height, PADDING_TOP)
        series = str(row.get(color_field, "series"))
        label = str(row.get("method_name") or row.get(color_field) or "point")
        parts.append(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="{color_map[series]}" opacity="0.86"/>')
        parts.append(f'  <text x="{x + 9:.2f}" y="{y - 9:.2f}" font-family="Arial, sans-serif" font-size="11" fill="#111827">{_escape(label)}</text>')
    parts.extend(_legend(color_map))
    return _svg_shell(str(figure.get("title", "figure")), "\n".join(parts))


def _axes(min_value: float, max_value: float) -> str:
    """绘制简化坐标轴和 y 轴范围标注。"""
    plot_height = SVG_HEIGHT - PADDING_TOP - PADDING_BOTTOM
    y_axis_x = PADDING_LEFT
    x_axis_y = PADDING_TOP + plot_height
    return f"""  <line x1="{PADDING_LEFT}" y1="{x_axis_y}" x2="{SVG_WIDTH - PADDING_RIGHT}" y2="{x_axis_y}" stroke="#9ca3af"/>
  <line x1="{y_axis_x}" y1="{PADDING_TOP}" x2="{y_axis_x}" y2="{x_axis_y}" stroke="#9ca3af"/>
  <text x="{PADDING_LEFT - 12}" y="{PADDING_TOP + 4}" font-family="Arial, sans-serif" font-size="11" fill="#6b7280" text-anchor="end">{max_value:.3g}</text>
  <text x="{PADDING_LEFT - 12}" y="{x_axis_y + 4}" font-family="Arial, sans-serif" font-size="11" fill="#6b7280" text-anchor="end">{min_value:.3g}</text>"""


def _legend(color_map: dict[str, str]) -> list[str]:
    """绘制图例。"""
    parts: list[str] = []
    for index, (label, color) in enumerate(color_map.items()):
        x = PADDING_LEFT + index * 150
        y = SVG_HEIGHT - 24
        parts.append(f'  <rect x="{x}" y="{y - 10}" width="12" height="12" fill="{color}"/>')
        parts.append(f'  <text x="{x + 18}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#374151">{_escape(label)}</text>')
    return parts


def _empty_message(message: str) -> str:
    """生成无数据提示。"""
    return f'  <text x="{SVG_WIDTH / 2}" y="{SVG_HEIGHT / 2}" font-family="Arial, sans-serif" font-size="18" fill="#6b7280" text-anchor="middle">{_escape(message)}</text>'


def render_figure_svg(figure: dict[str, Any]) -> str:
    """按 chart_type 将单个 figure spec 渲染为 SVG。"""
    chart_type = str(figure.get("chart_type", "bar"))
    if "scatter" in chart_type:
        return _render_scatter(figure)
    return _render_bar_like(figure)


def render_paper_figure_package(figure_specs: dict[str, Any], output_root: str | Path) -> dict[str, Any]:
    """渲染所有 figure specs, 并生成 HTML 报告。"""
    output_path = Path(output_root)
    figure_dir = output_path / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, str]] = []
    for figure in figure_specs.get("figures", []):
        if not isinstance(figure, dict):
            continue
        figure_id = str(figure.get("figure_id") or f"figure_{len(rendered) + 1}")
        file_name = f"{figure_id}.svg"
        svg_text = render_figure_svg(figure)
        (figure_dir / file_name).write_text(svg_text, encoding="utf-8")
        rendered.append(
            {
                "figure_id": figure_id,
                "title": str(figure.get("title") or figure_id),
                "chart_type": str(figure.get("chart_type") or "unknown"),
                "svg_path": f"figures/{file_name}",
            }
        )
    report = build_html_report(rendered, figure_specs)
    (output_path / "paper_figures_report.html").write_text(report, encoding="utf-8")
    manifest = {
        "artifact_name": "rendered_paper_figures_manifest.json",
        "figure_count": len(rendered),
        "rendered_figures": rendered,
        "report_path": "paper_figures_report.html",
    }
    (output_path / "rendered_paper_figures_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_html_report(rendered: list[dict[str, str]], figure_specs: dict[str, Any]) -> str:
    """构造论文图表 HTML 检查报告。"""
    cards = []
    specs_by_id = {
        str(figure.get("figure_id")): figure
        for figure in figure_specs.get("figures", [])
        if isinstance(figure, dict)
    }
    for item in rendered:
        spec = specs_by_id.get(item["figure_id"], {})
        takeaway = spec.get("takeaway", "") if isinstance(spec, dict) else ""
        cards.append(
            f"""<section class="card">
  <h2>{_escape(item["title"])}</h2>
  <p><strong>图表类型:</strong> {_escape(item["chart_type"])}</p>
  <p>{_escape(takeaway)}</p>
  <img src="{_escape(item["svg_path"])}" alt="{_escape(item["title"])}" />
</section>"""
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>CEG 论文图表报告</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111827; background: #f9fafb; }}
    .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
    img {{ max-width: 100%; border: 1px solid #e5e7eb; }}
  </style>
</head>
<body>
  <h1>CEG 论文图表报告</h1>
  <p>本报告由 figure specs 自动渲染, 用于检查主表、消融、baseline、质量指标和 bit recovery 图表。</p>
  {''.join(cards)}
</body>
</html>
"""
