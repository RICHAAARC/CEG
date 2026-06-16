"""从 preflight 报告生成真实 pilot 输入替换清单。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_replacement_checklist import (  # noqa: E402
    write_pilot_input_replacement_checklist,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="把 pilot 输入计划 preflight 报告转换为替换清单.")
    parser.add_argument("--preflight-report", required=True, help="pilot_input_plan_preflight_report.json 路径.")
    parser.add_argument("--out-json", required=True, help="替换清单 JSON 输出路径.")
    parser.add_argument("--out-md", default=None, help="替换清单 Markdown 输出路径.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    checklist = write_pilot_input_replacement_checklist(
        preflight_report_path=args.preflight_report,
        output_json_path=args.out_json,
        output_markdown_path=args.out_md,
    )
    print(json.dumps(checklist, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
