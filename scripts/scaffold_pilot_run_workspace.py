"""创建真实 pilot 输入准备工作区."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_run_workspace import scaffold_pilot_run_workspace  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器."""
    parser = argparse.ArgumentParser(description="创建 CEG 真实 pilot 输入准备工作区.")
    parser.add_argument("--checklist", required=True, help="pilot_readiness_checklist.json 路径.")
    parser.add_argument("--out", required=True, help="工作区输出目录.")
    parser.add_argument("--run-id", required=True, help="pilot run 标识.")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    manifest = scaffold_pilot_run_workspace(
        checklist_path=args.checklist,
        output_root=args.out,
        run_id=args.run_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
