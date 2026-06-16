"""从 CEG 论文输出目录导出 Markdown 结果报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.paper_report import write_paper_results_report


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG 论文结果 Markdown 报告。")
    parser.add_argument("--output-root", required=True, help="build_paper_outputs.py 生成的输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = write_paper_results_report(args.output_root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
