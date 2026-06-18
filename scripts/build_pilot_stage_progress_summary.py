"""构建真实 pilot 工作区阶段进度汇总。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_stage_progress_summary import MARKDOWN_NAME, REPORT_NAME, write_pilot_stage_progress_summary  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="汇总 CEG 真实 pilot 工作区阶段门禁进度。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--out-json", default=None, help="JSON 汇总输出路径。默认写入工作区。")
    parser.add_argument("--out-markdown", default=None, help="Markdown 汇总输出路径。默认写入工作区。")
    parser.add_argument("--require-pass", action="store_true", help="存在未通过阶段时返回非零退出码。")
    parser.add_argument(
        "--stage-scope",
        default="full_pilot",
        choices=["full_pilot", "image_generation_outputs"],
        help="阶段汇总范围。image_generation_outputs 只检查独立图像生成输出门禁。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    out_json = Path(args.out_json) if args.out_json else workspace / REPORT_NAME
    out_markdown = Path(args.out_markdown) if args.out_markdown else workspace / MARKDOWN_NAME
    summary = write_pilot_stage_progress_summary(workspace, out_json, out_markdown, stage_scope=args.stage_scope)
    print(
        json.dumps(
            {
                "artifact_name": summary["artifact_name"],
                "stage_scope": summary.get("stage_scope"),
                "overall_decision": summary["overall_decision"],
                "current_stage": summary["current_stage"],
                "recommended_next_action": summary["recommended_next_action"],
                "summary": summary["summary"],
                "out_json": str(out_json),
                "out_markdown": str(out_markdown),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and summary["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
