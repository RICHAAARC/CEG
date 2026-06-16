"""从论文 CSV 产物目录导出 LaTeX 表格。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.latex_tables import write_latex_tables_from_csv_dir


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG 论文 LaTeX 表格。")
    parser.add_argument("--artifacts", required=True, help="包含 CSV 表格的 artifacts 目录。")
    parser.add_argument("--out", required=True, help="LaTeX 表格输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = write_latex_tables_from_csv_dir(Path(args.artifacts), Path(args.out))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
