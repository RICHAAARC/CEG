"""校验 pilot paper_results_package 是否满足论文写作和 MyDrive 归档契约。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_paper_results_package_acceptance import write_pilot_paper_results_package_acceptance_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG pilot paper_results_package 输出接收门禁。")
    parser.add_argument("--package-root", required=True, help="已导出的 paper_results_package 目录。")
    parser.add_argument("--out", required=True, help="结果包输出接收门禁报告 JSON 输出路径。")
    parser.add_argument("--require-evidence", action="store_true", help="要求 paper/external evidence reports 存在且通过。")
    parser.add_argument("--require-image-examples", action="store_true", help="要求 image_example_manifest.json 及示例图存在。")
    parser.add_argument("--require-pass", action="store_true", help="门禁失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    report = write_pilot_paper_results_package_acceptance_report(
        args.package_root,
        args.out,
        require_evidence=args.require_evidence,
        require_image_examples=args.require_image_examples,
    )
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
