"""校验 pilot 输入 manifest 是否满足结果包构建前置契约."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_manifest import validate_pilot_input_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造 pilot 输入 manifest 校验命令行参数."""
    parser = argparse.ArgumentParser(description="校验 CEG pilot 输入 manifest.")
    parser.add_argument("--manifest", required=True, help="pilot_input_manifest.json 路径.")
    parser.add_argument("--out", default=None, help="可选校验报告输出路径.")
    parser.add_argument("--require-pass", action="store_true", help="校验未通过时返回非零退出码.")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    report = validate_pilot_input_manifest(args.manifest)
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
