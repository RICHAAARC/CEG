"""构建真实 pilot 输入 value pack 填写状态报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_value_pack_status import (  # noqa: E402
    STATUS_MARKDOWN_NAME,
    STATUS_REPORT_NAME,
    write_pilot_input_value_pack_status,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="汇总 CEG 真实 pilot 输入 value pack 的填写状态。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--value-pack", default=None, help="value pack JSON 路径。默认使用工作区内草稿。")
    parser.add_argument("--out-json", default=None, help="JSON 状态报告输出路径。默认写入工作区。")
    parser.add_argument("--out-markdown", default=None, help="Markdown 状态报告输出路径。默认写入工作区。")
    parser.add_argument("--require-pass", action="store_true", help="存在未填写或占位 value 时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    value_pack = Path(args.value_pack) if args.value_pack else None
    out_json = Path(args.out_json) if args.out_json else workspace / STATUS_REPORT_NAME
    out_markdown = Path(args.out_markdown) if args.out_markdown else workspace / STATUS_MARKDOWN_NAME
    report = write_pilot_input_value_pack_status(
        workspace_root=workspace,
        value_pack_path=value_pack,
        output_json_path=out_json,
        output_markdown_path=out_markdown,
    )
    print(
        json.dumps(
            {
                "artifact_name": report["artifact_name"],
                "overall_decision": report["overall_decision"],
                "recommended_next_stage": report["recommended_next_stage"],
                "summary": report["summary"],
                "out_json": str(out_json),
                "out_markdown": str(out_markdown),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
