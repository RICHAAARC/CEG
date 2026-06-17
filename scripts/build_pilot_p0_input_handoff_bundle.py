"""生成真实 pilot P0 输入用户交接包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_user_handoff_bundle import build_pilot_p0_input_handoff_bundle  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 CEG 真实 pilot P0 输入用户交接包。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--out", default=None, help="交接包输出目录。默认写入工作区 user_handoff/p0_input_handoff。")
    parser.add_argument(
        "--overwrite-fill-sheet",
        action="store_true",
        help="允许覆盖已有 CSV 填写表。默认不覆盖, 避免破坏人工填写内容。",
    )
    parser.add_argument("--require-pass", action="store_true", help="交接包预检未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    manifest = build_pilot_p0_input_handoff_bundle(
        workspace_root=args.workspace,
        output_root=args.out,
        overwrite_fill_sheet=args.overwrite_fill_sheet,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.require_pass and manifest["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
