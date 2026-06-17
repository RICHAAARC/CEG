"""生成 P2 图像生成 Colab GPU 交接清单。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_p2_gpu_handoff import write_p2_image_generation_gpu_handoff  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 CEG P2 图像生成 Colab GPU 交接清单。")
    parser.add_argument("--workspace", required=True, help="真实 pilot 工作区目录。")
    parser.add_argument("--handoff-root", default=None, help="交接清单输出目录。默认使用工作区 gpu_handoff/p2_image_generation。")
    parser.add_argument("--require-ready", action="store_true", help="清单未处于可交给 Colab 执行状态时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    checklist = write_p2_image_generation_gpu_handoff(
        workspace_root=args.workspace,
        handoff_root=args.handoff_root,
    )
    print(json.dumps(checklist, ensure_ascii=False, indent=2))
    if args.require_ready and checklist["overall_decision"] != "ready_for_user_colab_gpu_execution":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
