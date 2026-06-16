"""导出真实 pilot 输入 value pack CSV 填写表。"""

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
    export_pilot_input_value_pack_fill_sheet,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG 真实 pilot 输入 value pack CSV 填写表。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--out", default=None, help="CSV 填写表输出路径。默认写入工作区。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else workspace / VALUE_PACK_NAME
    output_csv = Path(args.out) if args.out else workspace / FILL_SHEET_NAME
    report = export_pilot_input_value_pack_fill_sheet(value_pack_path=value_pack, output_csv_path=output_csv)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
