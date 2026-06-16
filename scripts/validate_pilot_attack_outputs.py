"""校验 pilot attack 输出是否满足 detection 与统计流程契约。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_attack_output_acceptance import write_pilot_attack_output_acceptance_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG pilot attack 输出接收门禁。")
    parser.add_argument("--output-root", required=True, help="attack workflow 或外部 attack backend 输出根目录。")
    parser.add_argument("--out", required=True, help="attack 输出接收门禁报告 JSON 输出路径。")
    parser.add_argument("--require-pass", action="store_true", help="门禁失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    report = write_pilot_attack_output_acceptance_report(args.output_root, args.out)
    print(
        json.dumps(
            {
                "artifact_name": report["artifact_name"],
                "overall_decision": report["overall_decision"],
                "recommended_next_stage": report["recommended_next_stage"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
