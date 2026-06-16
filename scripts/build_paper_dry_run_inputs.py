"""生成 CEG 论文结果链路 dry-run 输入文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.paper_fixture_factory import write_paper_dry_run_inputs


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 CEG 论文 readiness dry-run 输入。")
    parser.add_argument("--out", required=True, help="输出输入文件的目录。")
    parser.add_argument("--repetitions", type=int, default=1, help="每个样本蓝图重复次数。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = write_paper_dry_run_inputs(args.out, repetitions=args.repetitions)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
