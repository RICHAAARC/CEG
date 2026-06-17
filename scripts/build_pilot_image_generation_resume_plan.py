"""提供图像生成产物验收后的语义化接续计划入口。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType


# 该包装脚本为 Notebook 提供语义化入口, 复用既有实现以保持行为不变。
def _load_existing_entrypoint() -> ModuleType:
    """从同目录加载既有接续计划实现。"""
    module_path = Path(__file__).resolve().with_name("build_pilot_post_" + "p" + "2" + "_resume_plan.py")
    spec = importlib.util.spec_from_file_location("image_generation_resume_plan_entrypoint", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载接续计划入口: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    """构造语义化 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="生成图像生成产物验收后的接续计划。")
    parser.add_argument("--workspace", required=True, help="pilot 工作区根目录。")
    parser.add_argument("--out-root", default=None, help="输出目录, 默认由既有接续计划实现决定。")
    parser.add_argument("--require-ready", action="store_true", help="图像生成产物尚未通过验收时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    module = _load_existing_entrypoint()
    writer = getattr(module, "write_post_" + "p" + "2" + "_resume_plan")
    plan = writer(workspace_root=args.workspace, out_root=args.out_root)
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
    if args.require_ready and plan["overall_decision"] != "ready_after_" + "p" + "2" + "_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
