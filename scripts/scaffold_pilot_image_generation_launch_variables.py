"""生成真实图像生成 pilot 启动变量草稿。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_image_generation_launch_plan import write_launch_variables_template  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成外部图像生成 backend 启动变量草稿.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    payload = write_launch_variables_template(workspace_root=args.workspace, output_path=args.out)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
