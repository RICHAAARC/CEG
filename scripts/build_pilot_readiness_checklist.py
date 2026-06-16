"""根据 pilot gap 报告生成真实 pilot 启动清单."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_readiness_checklist import (  # noqa: E402
    build_pilot_readiness_checklist,
    load_gap_report,
    render_pilot_readiness_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器."""
    parser = argparse.ArgumentParser(description="构建 CEG 真实 pilot 启动清单.")
    parser.add_argument("--gap-report", required=True, help="pilot_input_gap_report.json 路径.")
    parser.add_argument("--out", required=True, help="pilot_readiness_checklist.json 输出路径.")
    parser.add_argument("--markdown-out", default=None, help="可选 Markdown 清单输出路径.")
    parser.add_argument(
        "--require-formal-claims",
        action="store_true",
        help="要求 formal_result_claim 和 evidence_paths 也阻断 formal pilot.",
    )
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()

    gap_report = load_gap_report(args.gap_report)
    checklist = build_pilot_readiness_checklist(
        gap_report,
        require_formal_claims=args.require_formal_claims,
    )

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(checklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.markdown_out:
        markdown_path = Path(args.markdown_out)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_pilot_readiness_markdown(checklist), encoding="utf-8")

    print(json.dumps(checklist, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
