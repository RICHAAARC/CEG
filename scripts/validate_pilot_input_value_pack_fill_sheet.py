"""只读预检真实 pilot 输入 value pack CSV 填写表。

该 CLI 的作用是在人工作业或 Notebook 调度导入 value pack 之前, 先检查
`pilot_input_value_pack_fill_sheet.csv` 中的 `value_json` 是否已经全部填写并满足
基本类型约束。它不会回写 value pack, 因此可以安全用于 P0 输入冻结前的反复检查。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_value_pack import VALUE_PACK_NAME  # noqa: E402
from experiments.pilot_input_value_pack_sheet import (  # noqa: E402
    FILL_SHEET_NAME,
    VALIDATION_MARKDOWN_NAME,
    VALIDATION_REPORT_NAME,
    validate_and_write_pilot_input_value_pack_fill_sheet,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="只读预检 CEG 真实 pilot 输入 value pack CSV 填写表, 不回写 value pack。"
    )
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--fill-sheet", default=None, help="CSV 填写表路径。默认使用工作区内填写表。")
    parser.add_argument("--out-json", default=None, help="预检 JSON 报告路径。默认写入工作区。")
    parser.add_argument("--out-md", default=None, help="预检 Markdown 报告路径。默认写入工作区。")
    parser.add_argument("--require-pass", action="store_true", help="预检未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else workspace / VALUE_PACK_NAME
    fill_sheet = Path(args.fill_sheet) if args.fill_sheet else workspace / FILL_SHEET_NAME
    out_json = Path(args.out_json) if args.out_json else workspace / VALIDATION_REPORT_NAME
    out_md = Path(args.out_md) if args.out_md else workspace / VALIDATION_MARKDOWN_NAME

    report = validate_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack,
        input_csv_path=fill_sheet,
        report_path=out_json,
        markdown_report_path=out_md,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
