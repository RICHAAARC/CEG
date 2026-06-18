"""生成 SD3.5 外部扩散水印 baseline adapter 命令计划。

该脚本统一支持 Tree-Ring、Gaussian Shading 和 Shallow Diffuse。它只生成
`scripts/run_baseline_plan.py` 可执行的显式 argv 计划, 不实现任何 baseline 算法本体。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ADAPTERS = {
    "tree_ring": "external_baselines/main_table/tree_ring_watermark/adapter/run_ceg_eval.py",
    "gaussian_shading": "external_baselines/main_table/gaussian_shading/adapter/run_ceg_eval.py",
    "shallow_diffuse": "external_baselines/main_table/shallow_diffuse/adapter/run_ceg_eval.py",
}


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="生成 SD3.5 外部 baseline adapter plan。")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--methods", default="tree_ring,gaussian_shading,shallow_diffuse")
    parser.add_argument("--prompt-plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--output-root", required=True, help="各 baseline observation 和 artifact 的共同输出根目录。")
    parser.add_argument("--working-directory", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=86400)
    parser.add_argument("--model-id", default="stabilityai/stable-diffusion-3.5-medium")
    parser.add_argument("--torch-dtype", default="float16")
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--latent-channels", type=int, default=16)
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--num-inversion-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--require-cuda", action="store_true")
    return parser


def _selected_methods(value: str) -> list[str]:
    """解析 baseline 方法列表。"""

    methods = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in methods if item not in ADAPTERS]
    if unknown:
        raise ValueError(f"不支持的 SD3.5 external baseline: {unknown}")
    return methods


def build_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    """构造 baseline command plan。"""

    repo_root = Path(args.repo_root).resolve()
    prompt_plan = Path(args.prompt_plan).resolve()
    output_root = Path(args.output_root).resolve()
    working_directory = Path(args.working_directory).resolve() if args.working_directory else repo_root
    if not prompt_plan.is_file():
        raise FileNotFoundError(f"prompt plan 不存在: {prompt_plan}")

    rows: list[dict[str, Any]] = []
    for method_id in _selected_methods(args.methods):
        adapter_path = repo_root / ADAPTERS[method_id]
        if not adapter_path.is_file():
            raise FileNotFoundError(f"{method_id} adapter 不存在: {adapter_path}")
        method_root = output_root / method_id
        observation_output = method_root / "baseline_observations.json"
        artifact_root = method_root / "artifacts"
        command = [
            sys.executable,
            str(adapter_path),
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(observation_output),
            "--artifact-root",
            str(artifact_root),
            "--model-id",
            str(args.model_id),
            "--torch-dtype",
            str(args.torch_dtype),
            "--height",
            str(args.height),
            "--width",
            str(args.width),
            "--latent-channels",
            str(args.latent_channels),
            "--num-inference-steps",
            str(args.num_inference_steps),
            "--num-inversion-steps",
            str(args.num_inversion_steps),
            "--guidance-scale",
            str(args.guidance_scale),
            "--seed",
            str(args.seed),
        ]
        if str(args.attack_families).strip():
            command.extend(["--attack-families", str(args.attack_families)])
        if args.max_samples is not None:
            command.extend(["--max-samples", str(args.max_samples)])
        if args.require_cuda:
            command.append("--require-cuda")
        rows.append(
            {
                "baseline_id": method_id,
                "command": command,
                "output_path": str(observation_output),
                "working_directory": str(working_directory),
                "timeout_seconds": int(args.timeout_seconds),
            }
        )
    return rows


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    plan = build_plan(args)
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_root).resolve().mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_path": str(output_path), "row_count": len(plan), "methods": [row["baseline_id"] for row in plan]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
