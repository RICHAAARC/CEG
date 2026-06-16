"""执行外部图像生成命令计划并写出执行 manifest。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.image_generation_plan import (
    build_image_generation_plan_manifest,
    load_image_generation_command_plan,
    run_image_generation_command_plan,
)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="执行 CEG 外部图像生成命令计划。")
    parser.add_argument("--plan", required=True, help="image generation 命令计划 JSON / JSONL / CSV 文件。")
    parser.add_argument("--out", required=True, help="命令计划执行摘要输出目录。")
    parser.add_argument("--require-pass", action="store_true", help="任一 backend 输出契约失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    specs = load_image_generation_command_plan(args.plan)
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = build_image_generation_plan_manifest(specs)
    result = run_image_generation_command_plan(specs)
    (output_root / "image_generation_command_plan_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "image_generation_command_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "image_generation_backend_count": len(specs),
        "pass_count": result["pass_count"],
        "plan_manifest_path": "image_generation_command_plan_manifest.json",
        "command_results_path": "image_generation_command_results.json",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.require_pass and result["pass_count"] != len(specs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
