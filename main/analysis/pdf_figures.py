"""把论文 figure specs 导出为轻量 PDF 预览。

该模块使用标准库直接写出 PDF, 目标是提供最小可复现的论文图表 PDF 检查件。
更高保真图像仍由 SVG / HTML 渲染器负责; 本模块主要用于 release 包和无浏览器环境下的审计预览。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 54
TOP = 740
BAR_MAX_WIDTH = 360
BAR_HEIGHT = 14
BAR_GAP = 8


def _pdf_text(value: Any) -> str:
    """把文本转换为 PDF 内置字体可安全显示的 ASCII 子集。"""
    text = str(value).encode("ascii", errors="replace").decode("ascii")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _number(value: Any) -> float | None:
    """读取可绘制数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _line(text: str, x: int, y: int, size: int = 10) -> str:
    """生成 PDF 文本绘制指令。"""
    return f"BT /F1 {size} Tf {x} {y} Td ({_pdf_text(text)}) Tj ET\n"


def _rect(x: float, y: float, width: float, height: float, gray: float = 0.25) -> str:
    """生成 PDF 矩形绘制指令。"""
    return f"{gray:.2f} g {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f 0 g\n"


def _figure_page_stream(figure: dict[str, Any]) -> str:
    """把一个 figure spec 转换为单页 PDF 内容流。"""
    title = str(figure.get("title") or figure.get("figure_id") or "figure")
    chart_type = str(figure.get("chart_type") or "unknown")
    takeaway = str(figure.get("takeaway") or "")
    encodings = figure.get("encodings", {}) if isinstance(figure.get("encodings"), dict) else {}
    x_field = str(encodings.get("x", "method_name"))
    y_field = str(encodings.get("y", "metric_value"))
    data = [row for row in figure.get("data", []) if isinstance(row, dict)]
    drawable = [(str(row.get(x_field, row.get("method_name", "row"))), _number(row.get(y_field))) for row in data]
    drawable = [(label, value) for label, value in drawable if value is not None]
    max_value = max((abs(value) for _, value in drawable), default=1.0) or 1.0

    stream = []
    stream.append(_line(title, LEFT, TOP, 16))
    stream.append(_line(f"chart_type: {chart_type}", LEFT, TOP - 24, 10))
    stream.append(_line(f"takeaway: {takeaway[:120]}", LEFT, TOP - 42, 10))
    stream.append(_line(f"x: {x_field}    y: {y_field}", LEFT, TOP - 60, 10))
    if not drawable:
        stream.append(_line("No numeric rows are available for this figure preview.", LEFT, TOP - 100, 11))
        return "".join(stream)

    y = TOP - 100
    for index, (label, value) in enumerate(drawable[:22]):
        bar_width = abs(value) / max_value * BAR_MAX_WIDTH
        stream.append(_line(label[:32], LEFT, y + 2, 8))
        stream.append(_rect(LEFT + 170, y, bar_width, BAR_HEIGHT, gray=0.20 + (index % 5) * 0.08))
        stream.append(_line(f"{value:.4g}", LEFT + 170 + BAR_MAX_WIDTH + 12, y + 2, 8))
        y -= BAR_HEIGHT + BAR_GAP
    if len(drawable) > 22:
        stream.append(_line(f"... {len(drawable) - 22} rows omitted in PDF preview", LEFT, y - 4, 8))
    return "".join(stream)


def _build_pdf(page_streams: list[str]) -> bytes:
    """生成最小 PDF 字节流。"""
    objects: list[bytes] = []
    page_object_ids: list[int] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    pages_id = 2
    font_id = 3
    add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_object(b"PAGES_PLACEHOLDER")
    add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for stream in page_streams:
        stream_bytes = stream.encode("latin-1", errors="replace")
        content_id = add_object(b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"endstream")
        page_payload = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        page_id = add_object(page_payload)
        page_object_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def render_figure_specs_pdf(figure_specs: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    """把 figure specs 渲染为 PDF 文件并返回 manifest。"""
    figures = [figure for figure in figure_specs.get("figures", []) if isinstance(figure, dict)]
    page_streams = [_figure_page_stream(figure) for figure in figures] or [_line("No figure specs are available.", LEFT, TOP, 12)]
    pdf_bytes = _build_pdf(page_streams)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return {
        "artifact_name": "paper_figures_pdf_manifest.json",
        "pdf_path": path.name,
        "figure_count": len(figures),
        "page_count": len(page_streams),
        "byte_count": len(pdf_bytes),
    }


def render_figure_specs_pdf_package(figure_specs: dict[str, Any], output_root: str | Path) -> dict[str, Any]:
    """写出 PDF 图表预览和对应 manifest。"""
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest = render_figure_specs_pdf(figure_specs, output_path / "paper_figures_preview.pdf")
    (output_path / "paper_figures_pdf_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
