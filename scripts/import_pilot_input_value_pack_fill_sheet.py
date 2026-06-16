"""从 CSV 填写表导入真实 pilot 输入 value pack。"""

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
    IMPORT_REPORT_NAME,
    import_and_write_pilot_input_value_pack_fill_sheet,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="从 CSV 填写表导入 CEG 真实 pilot 输入 value pack。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--fill-sheet", default=None, help="CSV 填写表路径。默认使用工作区内填写表。")
    parser.add_argument("--out-value-pack", default=None, help="回写后的 value pack 路径。默认覆盖原 value pack。")
    parser.add_argument("--out-report", default=None, help="导入报告路径。默认写入工作区。")
    parser.add_argument("--require-pass", action="store_true", help="存在空值或 CSV 解析错误时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else workspace / VALUE_PACK_NAME
    fill_sheet = Path(args.fill_sheet) if args.fill_sheet else workspace / FILL_SHEET_NAME
    out_value_pack = Path(args.out_value_pack) if args.out_value_pack else None
    out_report = Path(args.out_report) if args.out_report else workspace / IMPORT_REPORT_NAME
    report = import_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack,
        input_csv_path=fill_sheet,
        output_value_pack_path=out_value_pack,
        report_path=out_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
