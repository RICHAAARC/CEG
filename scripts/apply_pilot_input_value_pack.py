"""把已填写的真实 pilot 输入值包应用到工作区计划文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_value_pack import (  # noqa: E402
    VALUE_PACK_APPLICATION_REPORT_NAME,
    apply_and_write_pilot_input_value_pack,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="把真实 pilot 输入值包应用到 prompt、split、seed、model 和 watermark 计划.")
    parser.add_argument("--workspace", required=True, help="真实 pilot 输入工作区路径.")
    parser.add_argument("--value-pack", required=True, help="已填写 value 字段的值包 JSON.")
    parser.add_argument("--out", default=None, help="应用报告输出路径.")
    parser.add_argument("--require-pass", action="store_true", help="如果值包未完整填写则返回非 0.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    output_path = Path(args.out) if args.out else Path(args.workspace) / VALUE_PACK_APPLICATION_REPORT_NAME
    report = apply_and_write_pilot_input_value_pack(
        workspace_root=args.workspace,
        value_pack_path=args.value_pack,
        report_path=output_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
