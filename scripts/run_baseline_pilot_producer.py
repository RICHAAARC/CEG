"""从 detection_events.json 生成外部 baseline pilot observations。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.baseline_pilot_producer import write_baseline_pilot_outputs


def _load_events(path: Path) -> list[dict[str, object]]:
    """读取 detection events JSON 数组。"""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise TypeError("detection events JSON must contain a list")
    return [dict(row) for row in payload]


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成外部 baseline pilot observation 契约产物。")
    parser.add_argument("--events", required=True, help="detection_events.json 路径。")
    parser.add_argument("--out", required=True, help="baseline pilot 输出目录。")
    parser.add_argument(
        "--baseline-id",
        action="append",
        default=None,
        help="可重复指定 baseline id。未指定时使用注册表中的全部外部 baseline。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    events_path = Path(args.events)
    manifest = write_baseline_pilot_outputs(
        _load_events(events_path),
        args.out,
        events_path=events_path,
        baseline_ids=args.baseline_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
