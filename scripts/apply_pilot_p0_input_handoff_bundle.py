"""验证并应用真实 pilot P0 输入用户交接包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_user_handoff_bundle import apply_pilot_p0_input_handoff_bundle  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="验证并应用 CEG 真实 pilot P0 输入用户交接包。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--handoff-root", default=None, help="交接包目录。默认使用工作区 user_handoff/p0_input_handoff。")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证交接包内 CSV, 不同步 canonical CSV, 不导入 value pack。",
    )
    parser.add_argument("--require-pass", action="store_true", help="交接包应用未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    report = apply_pilot_p0_input_handoff_bundle(
        workspace_root=args.workspace,
        handoff_root=args.handoff_root,
        write_on_pass=not args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
