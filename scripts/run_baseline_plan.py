"""执行外部 baseline 命令计划并汇总 observation 输出。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.baseline_command_adapter import run_baseline_commands
from experiments.baseline_plan import build_baseline_plan_manifest, load_baseline_command_plan


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行 CEG 外部 baseline 命令计划。")
    parser.add_argument("--plan", required=True, help="baseline 命令计划 JSON / JSONL / CSV。")
    parser.add_argument("--out", required=True, help="输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    specs = load_baseline_command_plan(Path(args.plan))
    results, rows = run_baseline_commands(specs)
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "baseline_command_plan_manifest.json").write_text(
        json.dumps(build_baseline_plan_manifest(specs), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "baseline_command_results.json").write_text(
        json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "baseline_observations.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"command_count": len(specs), "observation_count": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
