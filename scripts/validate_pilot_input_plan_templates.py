"""校验真实 pilot 输入计划模板是否仍含占位字段。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_plan_preflight import (  # noqa: E402
    PREFLIGHT_REPORT_NAME,
    write_pilot_input_plan_preflight_report,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG 真实 pilot 输入计划是否可启动真实运行.")
    parser.add_argument("--workspace", required=True, help="真实 pilot 输入工作区路径.")
    parser.add_argument(
        "--out",
        default=None,
        help="预检报告输出路径. 默认写入工作区根目录的 pilot_input_plan_preflight_report.json.",
    )
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="如果预检不通过则返回非 0 退出码, 用于真实运行前的硬门禁.",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    output_path = Path(args.out) if args.out else Path(args.workspace) / PREFLIGHT_REPORT_NAME
    report = write_pilot_input_plan_preflight_report(
        workspace_root=args.workspace,
        output_path=output_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
