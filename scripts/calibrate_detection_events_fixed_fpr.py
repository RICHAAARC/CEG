"""从 detection_events.json 校准 fixed FPR 阈值并回写事件 payload。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.detection_event_thresholds import (
    DEFAULT_CALIBRATION_SPLIT,
    DEFAULT_SCORE_FIELD,
    DEFAULT_TARGET_FPR,
    load_detection_events,
    write_calibrated_detection_event_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="校准 detection events 的 fixed FPR 阈值并回写 payload.thresholds。")
    parser.add_argument("--events", required=True, help="detection_events.json 路径。")
    parser.add_argument("--out", required=True, help="输出目录。")
    parser.add_argument("--target-fpr", type=float, default=DEFAULT_TARGET_FPR, help="目标 clean negative FPR。")
    parser.add_argument("--score-field", default=DEFAULT_SCORE_FIELD, help="payload.content 中用于校准的分数字段。")
    parser.add_argument("--calibration-split", default=DEFAULT_CALIBRATION_SPLIT, help="优先用于校准的 split。")
    parser.add_argument(
        "--negative-role",
        action="append",
        default=None,
        help="用于校准的负样本角色, 可重复传入。默认 clean_negative。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    report = write_calibrated_detection_event_outputs(
        load_detection_events(args.events),
        args.out,
        target_fpr=args.target_fpr,
        score_field=args.score_field,
        calibration_split=args.calibration_split,
        negative_roles=tuple(args.negative_role or ["clean_negative"]),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
