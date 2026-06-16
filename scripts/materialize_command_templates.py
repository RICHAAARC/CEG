"""从命令模板生成 baseline 或高级指标命令计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.command_templates import (
    materialize_baseline_command_plan,
    materialize_detection_command_plan,
    materialize_image_generation_command_plan,
    materialize_metric_command_plan,
)


def _variables_from_args(values: list[str]) -> dict[str, str]:
    """解析 key=value 形式的模板变量。"""
    variables: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"template variable must use key=value format: {item}")
        key, value = item.split("=", 1)
        variables[key] = value
    return variables


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="物化 CEG 外部命令模板。")
    parser.add_argument("--templates", required=True, help="命令模板 JSON 文件。")
    parser.add_argument("--kind", choices=("baseline", "metric", "image_generation", "detection"), required=True, help="模板类型。")
    parser.add_argument("--out", required=True, help="输出命令计划 JSON 文件。")
    parser.add_argument("--var", action="append", default=[], help="模板变量, 格式为 key=value, 可重复。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    variables = _variables_from_args(args.var)
    if args.kind == "baseline":
        specs = materialize_baseline_command_plan(args.templates, variables)
        rows = [
            {
                "baseline_id": spec.baseline_id,
                "command": list(spec.command),
                "output_path": spec.output_path,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
            }
            for spec in specs
        ]
    elif args.kind == "metric":
        rows = materialize_metric_command_plan(args.templates, variables)
    elif args.kind == "image_generation":
        specs = materialize_image_generation_command_plan(args.templates, variables)
        rows = [
            {
                "backend_id": spec.backend_id,
                "command": list(spec.command),
                "output_root": spec.output_root,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
            }
            for spec in specs
        ]
    else:
        specs = materialize_detection_command_plan(args.templates, variables)
        rows = [
            {
                "detector_id": spec.detector_id,
                "command": list(spec.command),
                "output_root": spec.output_root,
                "working_directory": spec.working_directory,
                "timeout_seconds": spec.timeout_seconds,
            }
            for spec in specs
        ]
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_path": str(output_path), "row_count": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
