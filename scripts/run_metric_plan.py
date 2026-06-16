"""执行外部高级指标命令计划并汇总 metric rows。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metric_plan import build_metric_plan_manifest, load_metric_command_plan, run_metric_command_plan


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="执行 CEG 外部高级指标命令计划。")
    parser.add_argument("--plan", required=True, help="metric 命令计划 JSON / JSONL / CSV 文件。")
    parser.add_argument("--out", required=True, help="输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    specs = load_metric_command_plan(args.plan)
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = build_metric_plan_manifest(specs)
    result = run_metric_command_plan(specs)
    (output_root / "metric_command_plan_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "metric_command_results.json").write_text(
        json.dumps(result["results"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "metric_rows.json").write_text(
        json.dumps(result["metric_rows"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "metric_command_count": len(specs),
        "metric_row_count": len(result["metric_rows"]),
        "metric_rows_path": "metric_rows.json",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
