"""从 prompt plan 运行 mock 图像生成 backend。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.image_generation_backend import write_mock_image_generation_from_prompt_plan


def _load_prompt_rows(path: Path) -> list[dict[str, object]]:
    """读取 JSON / JSONL / CSV prompt plan。"""
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("prompt plan JSON must contain a list")
        return [dict(row) for row in payload]
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported prompt plan extension: {path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行 CEG mock 图像生成 backend。")
    parser.add_argument("--prompt-plan", required=True, help="prompt_plan.json / jsonl / csv 路径。")
    parser.add_argument("--out", required=True, help="mock 图像生成输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    manifest = write_mock_image_generation_from_prompt_plan(_load_prompt_rows(Path(args.prompt_plan)), args.out)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
