"""导出 CEG 论文结果输出包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.result_package import export_paper_results_package, validate_paper_results_package


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG 论文结果输出包。")
    parser.add_argument("--source-output-root", required=True, help="build_paper_outputs.py 生成的论文输出目录。")
    parser.add_argument("--package-root", required=True, help="结果包导出目录。")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="允许 readiness 未通过的输出目录进入调试包。默认要求 readiness pass。",
    )
    return parser


def main() -> None:
    """CLI 入口, 导出结果包并立即校验 manifest。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = export_paper_results_package(
        args.source_output_root,
        args.package_root,
        require_readiness=not args.allow_incomplete,
    )
    validation = validate_paper_results_package(args.package_root)
    (Path(args.package_root) / "paper_results_package_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"manifest": manifest, "validation": validation}, ensure_ascii=False, indent=2))
    if validation["overall_decision"] != "pass" and not args.allow_incomplete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
