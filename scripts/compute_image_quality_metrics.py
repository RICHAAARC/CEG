"""从图像配对清单计算论文图像质量指标。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.image_metrics import build_quality_metric_rows


def _load_pairs(path: Path) -> list[dict[str, str]]:
    """读取 JSON / JSONL / CSV 图像配对清单。"""
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("pairs JSON must contain a list")
        return [dict(row) for row in payload]
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported pairs file extension: {path.suffix}")


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    """按输出扩展名写出 JSON / JSONL / CSV 指标行。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    if path.suffix == ".jsonl":
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        return
    if path.suffix == ".csv":
        fieldnames = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return
    raise ValueError(f"unsupported output extension: {path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="计算图像水印论文质量指标。")
    parser.add_argument("--pairs", required=True, help="图像配对清单, 支持 JSON / JSONL / CSV。")
    parser.add_argument("--out", required=True, help="质量指标输出路径, 支持 JSON / JSONL / CSV。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    rows = build_quality_metric_rows(_load_pairs(Path(args.pairs)))
    _write_rows(Path(args.out), rows)
    print(json.dumps({"row_count": len(rows), "output_path": args.out}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
