"""导出论文实验矩阵。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.experiment_matrix import expand_experiment_matrix, load_experiment_matrix_config, write_experiment_matrix


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="构建 CEG 论文实验矩阵。")
    parser.add_argument("--config", default=None, help="可选实验矩阵 JSON 配置。")
    parser.add_argument("--out", required=True, help="输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    config = load_experiment_matrix_config(args.config) if args.config else None
    cells = expand_experiment_matrix(config)
    manifest = write_experiment_matrix(args.out, cells)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
