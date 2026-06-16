"""从真实实验样本清单构建 CEG 协议事件输入。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.sample_manifest import write_protocol_event_inputs_from_sample_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="把样本清单转换为 CEG 协议 events.json。")
    parser.add_argument("--samples", required=True, help="样本清单路径, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--thresholds", required=True, help="阈值 JSON 映射路径。")
    parser.add_argument("--out", required=True, help="输出目录, 会写出 events.json 和 image_pairs.json。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = write_protocol_event_inputs_from_sample_manifest(args.samples, args.thresholds, args.out)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
