"""校验 CEG 论文输出目录是否达到 paper readiness。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.paper_readiness import load_paper_output_requirements, write_paper_readiness_report


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG 论文输出目录完整性。")
    parser.add_argument("--output-root", required=True, help="build_paper_outputs.py 生成的输出目录。")
    parser.add_argument("--requirements", default=None, help="可选 paper output requirements JSON。")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="只写出 readiness 报告, 即使未通过也不返回失败退出码。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    requirements = load_paper_output_requirements(args.requirements) if args.requirements else None
    report = write_paper_readiness_report(args.output_root, requirements=requirements)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["overall_decision"] != "pass" and not args.allow_incomplete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
