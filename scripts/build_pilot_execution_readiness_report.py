"""生成真实 pilot 执行就绪聚合报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_execution_readiness import (  # noqa: E402
    EXECUTION_READINESS_REPORT_NAME,
    write_pilot_execution_readiness_report,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="聚合 pilot 输入门禁并判断是否可启动真实图像生成.")
    parser.add_argument("--workspace", required=True, help="真实 pilot 输入工作区路径.")
    parser.add_argument("--out", default=None, help="执行就绪报告输出路径.")
    parser.add_argument("--require-pass", action="store_true", help="如果尚未就绪则返回非 0.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    output_path = Path(args.out) if args.out else Path(args.workspace) / EXECUTION_READINESS_REPORT_NAME
    report = write_pilot_execution_readiness_report(workspace_root=args.workspace, output_path=output_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
