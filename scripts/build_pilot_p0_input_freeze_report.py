"""运行真实 pilot P0 输入冻结聚合门禁。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_value_pack import VALUE_PACK_NAME  # noqa: E402
from experiments.pilot_input_value_pack_sheet import FILL_SHEET_NAME  # noqa: E402
from experiments.pilot_p0_input_freeze import (  # noqa: E402
    P0_INPUT_FREEZE_MARKDOWN_NAME,
    P0_INPUT_FREEZE_REPORT_NAME,
    write_pilot_p0_input_freeze_report,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行 CEG pilot P0 输入冻结聚合门禁。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--fill-sheet", default=None, help="CSV 填写表路径。默认使用工作区内填写表。")
    parser.add_argument("--out-json", default=None, help="JSON 报告输出路径。默认写入工作区。")
    parser.add_argument("--out-md", default=None, help="Markdown 报告输出路径。默认写入工作区。")
    parser.add_argument("--require-pass", action="store_true", help="聚合门禁未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else workspace / VALUE_PACK_NAME
    fill_sheet = Path(args.fill_sheet) if args.fill_sheet else workspace / FILL_SHEET_NAME
    out_json = Path(args.out_json) if args.out_json else workspace / P0_INPUT_FREEZE_REPORT_NAME
    out_md = Path(args.out_md) if args.out_md else workspace / P0_INPUT_FREEZE_MARKDOWN_NAME
    report = write_pilot_p0_input_freeze_report(
        workspace_root=workspace,
        value_pack_path=value_pack,
        fill_sheet_path=fill_sheet,
        output_json_path=out_json,
        output_markdown_path=out_md,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
