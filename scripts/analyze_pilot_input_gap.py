"""生成 pilot 输入缺口审计报告的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_gap import analyze_pilot_input_gap


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    parser = argparse.ArgumentParser(description="审计 pilot_input_manifest.json 距离真实或正式 pilot 的输入缺口.")
    parser.add_argument("--manifest", required=True, help="pilot_input_manifest.json 路径.")
    parser.add_argument("--out", default=None, help="可选 JSON 报告输出路径.")
    parser.add_argument("--require-formal-claims", action="store_true", help="要求 execution manifest 均声明 formal_result_claim 和 evidence_paths.")
    parser.add_argument("--require-ready", action="store_true", help="若报告不是 pass 则以非零退出码阻断后续流程.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    report = analyze_pilot_input_gap(args.manifest, require_formal_claims=args.require_formal_claims)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.require_ready and report.get("overall_decision") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
