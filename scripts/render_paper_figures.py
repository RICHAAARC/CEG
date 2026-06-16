"""将 paper_figure_specs.json 渲染为 SVG 图表和 HTML 报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.render_figures import render_paper_figure_package


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="渲染 CEG 论文图表。")
    parser.add_argument("--figure-specs", required=True, help="paper_figure_specs.json 路径。")
    parser.add_argument("--out", required=True, help="渲染输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    specs = json.loads(Path(args.figure_specs).read_text(encoding="utf-8-sig"))
    manifest = render_paper_figure_package(specs, Path(args.out))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
