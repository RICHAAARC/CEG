"""生成 P2 通过后的 P3 / P4 接续计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_post_p2_resume_plan import write_post_p2_resume_plan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 P2 通过后的 P3 / P4 接续计划。")
    parser.add_argument("--workspace", required=True, help="pilot 工作区根目录。")
    parser.add_argument("--out-root", default=None, help="输出目录, 默认写入 workspace/gpu_handoff/post_p2_resume。")
    parser.add_argument("--require-ready", action="store_true", help="P2 未通过时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    plan = write_post_p2_resume_plan(workspace_root=args.workspace, out_root=args.out_root)
    print(
        json.dumps(
            {
                "artifact_name": plan["artifact_name"],
                "overall_decision": plan["overall_decision"],
                "summary": plan["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_ready and plan["overall_decision"] != "ready_after_p2_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
