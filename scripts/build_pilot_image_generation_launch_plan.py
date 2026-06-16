"""生成真实图像生成 pilot 启动命令计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_launch_plan import (  # noqa: E402
    IMAGE_GENERATION_COMMAND_PLAN_NAME,
    LAUNCH_PLAN_REPORT_NAME,
    write_pilot_image_generation_launch_plan,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="在 readiness 通过后物化 image generation 命令计划.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--readiness-report", default=None)
    parser.add_argument("--launch-variables", required=True)
    parser.add_argument("--templates", default="configs/external_image_generation_command_templates.json")
    parser.add_argument("--out-report", default=None)
    parser.add_argument("--out-plan", default=None)
    parser.add_argument("--require-pass", action="store_true")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    workspace = Path(args.workspace)
    report_path = Path(args.out_report) if args.out_report else workspace / LAUNCH_PLAN_REPORT_NAME
    command_plan_path = Path(args.out_plan) if args.out_plan else workspace / IMAGE_GENERATION_COMMAND_PLAN_NAME
    readiness_report = Path(args.readiness_report) if args.readiness_report else workspace / "pilot_execution_readiness_report.json"
    report = write_pilot_image_generation_launch_plan(
        workspace_root=workspace,
        readiness_report_path=readiness_report,
        launch_variables_path=args.launch_variables,
        template_path=args.templates,
        report_path=report_path,
        command_plan_path=command_plan_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
