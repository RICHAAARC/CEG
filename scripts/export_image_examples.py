"""从 image_pairs.json 导出论文示例图和图像 manifest。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.image_examples import export_image_example_package


def _load_rows(path: Path) -> list[dict[str, object]]:
    """读取 JSON / JSONL / CSV 格式的 image pair rows。"""
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("image pairs JSON must contain a list")
        return [dict(row) for row in payload]
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported image pairs extension: {path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="导出论文结果包中的示例图和图像 manifest。")
    parser.add_argument("--image-pairs", required=True, help="image_pairs.json / jsonl / csv 路径。")
    parser.add_argument("--out", required=True, help="论文输出目录或 paper_results_package 源目录。")
    parser.add_argument("--max-examples-per-role", type=int, default=8)
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    manifest = export_image_example_package(
        _load_rows(Path(args.image_pairs)),
        args.out,
        max_examples_per_role=args.max_examples_per_role,
    )
    print(json.dumps({"example_count": manifest["example_count"], "role_counts": manifest["role_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
