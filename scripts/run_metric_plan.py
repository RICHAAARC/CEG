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
from main.core.digest import build_stable_digest


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
    metric_fields = sorted(
        {
            key
            for row in result["metric_rows"]
            for key in row
            if key not in {"event_id", "method_name", "baseline_id"}
        }
    )
    execution_manifest = {
        "artifact_name": "metric_execution_manifest.json",
        "producer_id": "external_metric_command_plan_runner",
        "producer_role": "external_metric_command_execution",
        "formal_result_claim": False,
        "execution_boundary": "external_metric_results_require_separate_formal_evidence",
        "metric_command_count": len(specs),
        "metric_row_count": len(result["metric_rows"]),
        "metric_names": sorted({spec.metric_name for spec in specs}),
        "metric_fields": metric_fields,
        "metric_rows_path": str(output_root / "metric_rows.json"),
        "command_results_path": str(output_root / "metric_command_results.json"),
        "execution_digest": build_stable_digest(
            {
                "specs": [spec.to_dict() for spec in specs],
                "results": result["results"],
                "rows": result["metric_rows"],
            }
        ),
    }
    (output_root / "metric_execution_manifest.json").write_text(
        json.dumps(execution_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "metric_command_count": len(specs),
        "metric_row_count": len(result["metric_rows"]),
        "metric_rows_path": "metric_rows.json",
        "metric_execution_manifest_path": "metric_execution_manifest.json",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
