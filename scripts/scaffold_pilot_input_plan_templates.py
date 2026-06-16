"""在真实 pilot 工作区生成输入计划模板."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器."""
    parser = argparse.ArgumentParser(description="生成 CEG 真实 pilot 输入计划模板.")
    parser.add_argument("--workspace", required=True, help="真实 pilot 输入工作区路径.")
    parser.add_argument("--run-id", required=True, help="pilot run 标识.")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    manifest = scaffold_pilot_input_plan_templates(
        workspace_root=args.workspace,
        run_id=args.run_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
