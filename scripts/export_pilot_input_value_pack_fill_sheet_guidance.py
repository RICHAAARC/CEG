"""导出真实 pilot 输入 value_json 填写指南。"""

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
    GUIDANCE_JSON_NAME,
    GUIDANCE_MARKDOWN_NAME,
    export_pilot_input_value_pack_fill_sheet_guidance,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出 CEG pilot value_json 填写指南。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--out-md", default=None, help="Markdown 填写指南输出路径。默认写入工作区。")
    parser.add_argument("--out-json", default=None, help="JSON 填写指南输出路径。默认写入工作区。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else workspace / VALUE_PACK_NAME
    out_md = Path(args.out_md) if args.out_md else workspace / GUIDANCE_MARKDOWN_NAME
    out_json = Path(args.out_json) if args.out_json else workspace / GUIDANCE_JSON_NAME
    report = export_pilot_input_value_pack_fill_sheet_guidance(
        value_pack_path=value_pack,
        output_markdown_path=out_md,
        output_json_path=out_json,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
