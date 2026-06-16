"""从 paper_figure_specs.json 导出轻量 PDF 图表预览。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.pdf_figures import render_figure_specs_pdf_package


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG 论文图表 PDF 预览。")
    parser.add_argument("--figure-specs", required=True, help="paper_figure_specs.json 路径。")
    parser.add_argument("--out", required=True, help="输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    figure_specs = json.loads(Path(args.figure_specs).read_text(encoding="utf-8-sig"))
    manifest = render_figure_specs_pdf_package(figure_specs, args.out)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
