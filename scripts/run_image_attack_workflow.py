"""运行轻量图像攻击 workflow 并写出 attack manifests。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.attack_images import run_attack_workflow


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
    parser = argparse.ArgumentParser(description="运行 CEG 论文图像攻击 workflow。")
    parser.add_argument("--image-pairs", required=True, help="image_pairs.json / jsonl / csv 路径。")
    parser.add_argument("--out", required=True, help="attack workflow 输出目录。")
    parser.add_argument(
        "--attack-families",
        default="brightness_contrast,gaussian_noise",
        help="逗号分隔的 attack family 列表。",
    )
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    manifest = run_attack_workflow(
        _load_rows(Path(args.image_pairs)),
        args.out,
        attack_families=[item.strip() for item in args.attack_families.split(",") if item.strip()],
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
