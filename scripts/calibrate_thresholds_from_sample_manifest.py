"""从样本清单校准 CEG 内容阈值。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.sample_manifest import load_sample_manifest
from experiments.threshold_calibration import (
    DEFAULT_CALIBRATION_SPLIT,
    DEFAULT_SCORE_FIELD,
    DEFAULT_TARGET_FPR,
    write_threshold_calibration_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="从 calibration 样本清单校准 CEG 内容阈值。")
    parser.add_argument("--samples", required=True, help="样本清单路径, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--out", required=True, help="输出目录, 会写出 thresholds.json 和 threshold_calibration_report.json。")
    parser.add_argument("--target-fpr", type=float, default=DEFAULT_TARGET_FPR, help="clean negative calibration 目标 FPR。")
    parser.add_argument("--score-field", default=DEFAULT_SCORE_FIELD, help="用于校准的分数字段。")
    parser.add_argument("--calibration-split", default=DEFAULT_CALIBRATION_SPLIT, help="用于校准的 split 名称。")
    parser.add_argument(
        "--negative-role",
        action="append",
        default=None,
        help="用于校准 FPR 的负样本角色, 可重复传入。默认只使用 clean_negative。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    report = write_threshold_calibration_outputs(
        load_sample_manifest(args.samples),
        args.out,
        target_fpr=args.target_fpr,
        score_field=args.score_field,
        calibration_split=args.calibration_split,
        negative_roles=tuple(args.negative_role or ["clean_negative"]),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
