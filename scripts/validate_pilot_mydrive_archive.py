"""校验 MyDrive 风格 paper_results_package 归档输出。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_mydrive_archive_acceptance import write_pilot_mydrive_archive_acceptance_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG MyDrive paper_results_package 归档输出接收门禁。")
    parser.add_argument("--drive-root", required=True, help="Drive 风格归档根目录, 如 D:/content/drive/MyDrive/CEG。")
    parser.add_argument("--out", required=True, help="MyDrive 归档接收门禁报告 JSON 输出路径。")
    parser.add_argument("--run-id", default=None, help="可选 run_id, 用于定位对应 archive manifest。")
    parser.add_argument("--manifest", default=None, help="可选显式 archive manifest 路径。")
    parser.add_argument("--allow-invalid-package", action="store_true", help="允许 package validation 非 pass 的调试归档。")
    parser.add_argument("--require-pass", action="store_true", help="门禁失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    report = write_pilot_mydrive_archive_acceptance_report(
        args.drive_root,
        args.out,
        run_id=args.run_id,
        manifest_path=args.manifest,
        require_package_validation=not args.allow_invalid_package,
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
