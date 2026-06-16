"""校验论文实验矩阵覆盖率。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.experiment_coverage import (
    build_experiment_coverage_report,
    load_event_records,
    load_experiment_matrix_cells,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 CEG 论文实验矩阵覆盖率。")
    parser.add_argument("--records", required=True, help="event_records.json 路径。")
    parser.add_argument("--matrix", required=True, help="experiment_matrix.json 路径。")
    parser.add_argument("--profile", required=True, help="当前论文 profile。")
    parser.add_argument("--out", required=True, help="覆盖率报告输出路径。")
    parser.add_argument("--require-complete", action="store_true", help="覆盖率未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    report = build_experiment_coverage_report(
        load_event_records(args.records),
        load_experiment_matrix_cells(args.matrix),
        profile=args.profile,
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_complete and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
