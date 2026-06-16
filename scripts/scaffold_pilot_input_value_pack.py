"""生成真实 pilot 输入值包草稿。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_value_pack import write_pilot_input_value_pack_template  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="基于替换清单生成集中填写的真实 pilot 输入值包.")
    parser.add_argument("--replacement-checklist", required=True, help="pilot_input_plan_replacement_checklist.json 路径.")
    parser.add_argument("--out", required=True, help="值包草稿输出路径.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    value_pack = write_pilot_input_value_pack_template(
        replacement_checklist_path=args.replacement_checklist,
        output_path=args.out,
    )
    print(json.dumps(value_pack, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
