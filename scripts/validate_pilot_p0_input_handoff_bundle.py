"""验证真实 pilot P0 输入用户交接包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_user_handoff_bundle import (  # noqa: E402
    P0_HANDOFF_ACCEPTANCE_REPORT_NAME,
    validate_pilot_p0_input_handoff_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="验证 CEG 真实 pilot P0 输入用户交接包。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--handoff-root", default=None, help="交接包目录。默认使用工作区 user_handoff/p0_input_handoff。")
    parser.add_argument("--out", default=None, help="验收报告输出路径。默认写入交接包目录。")
    parser.add_argument("--require-apply-report", action="store_true", help="要求交接包内已有 apply 报告。")
    parser.add_argument("--require-pass", action="store_true", help="交接包验收未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    handoff_root = Path(args.handoff_root) if args.handoff_root else None
    out = Path(args.out) if args.out else (
        (handoff_root / P0_HANDOFF_ACCEPTANCE_REPORT_NAME) if handoff_root is not None else None
    )
    report = validate_pilot_p0_input_handoff_bundle(
        workspace_root=args.workspace,
        handoff_root=handoff_root,
        output_path=out,
        require_apply_report=args.require_apply_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
