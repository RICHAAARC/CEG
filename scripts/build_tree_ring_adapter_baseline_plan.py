"""生成 Tree-Ring SD3.5 adapter 的 CEG 外部 baseline 命令计划。

该脚本只负责把仓库内的 Tree-Ring adapter 入口、prompt plan 和输出路径组织为
`scripts/run_baseline_plan.py` 可执行的显式 argv 计划。它不运行 Tree-Ring 算法本体,
也不把外部 baseline 逻辑放入 CEG 主方法层。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="生成 Tree-Ring SD3.5 adapter baseline plan。")
    parser.add_argument("--repo-root", required=True, help="CEG 仓库根目录。")
    parser.add_argument("--prompt-plan", required=True, help="CEG prompt plan JSON 路径。")
    parser.add_argument("--out", required=True, help="输出 baseline plan JSON 路径。")
    parser.add_argument("--observation-output", required=True, help="Tree-Ring adapter 应写出的 observation JSON 路径。")
    parser.add_argument("--artifact-root", required=True, help="Tree-Ring 图像、攻击结果和 manifest 输出目录。")
    parser.add_argument("--working-directory", default=None, help="执行 adapter 命令时使用的工作目录。缺省时使用 repo-root。")
    parser.add_argument("--timeout-seconds", type=int, default=86400, help="adapter 命令超时时间。")
    parser.add_argument("--model-id", default="stabilityai/stable-diffusion-3.5-medium", help="Hugging Face 模型 ID。")
    parser.add_argument("--torch-dtype", default="float16", help="模型 dtype, 例如 float16/bfloat16/float32。")
    parser.add_argument("--height", type=int, default=512, help="生成图像高度。")
    parser.add_argument("--width", type=int, default=512, help="生成图像宽度。")
    parser.add_argument("--latent-channels", type=int, default=16, help="SD3.5 latent 通道数。")
    parser.add_argument("--num-inference-steps", type=int, default=28, help="生成采样步数。")
    parser.add_argument("--num-inversion-steps", type=int, default=28, help="反演步数。")
    parser.add_argument("--guidance-scale", type=float, default=7.0, help="生成 guidance scale。")
    parser.add_argument("--seed", type=int, default=0, help="样本生成随机种子。")
    parser.add_argument("--watermark-seed", type=int, default=999999, help="Tree-Ring key 随机种子。")
    parser.add_argument("--w-channel", type=int, default=0, help="写入通道, -1 表示全部通道。")
    parser.add_argument("--w-radius", type=int, default=10, help="傅里叶域写入半径。")
    parser.add_argument("--w-pattern", default="ring", choices=["ring", "rand", "zeros"], help="Tree-Ring key 模式。")
    parser.add_argument("--threshold", type=float, default=None, help="显式阈值。缺失时由 adapter 从 calibration 样本派生。")
    parser.add_argument("--attack-families", default="", help="逗号分隔攻击族, 例如 jpeg,rotate。为空则只评估 clean。")
    parser.add_argument("--max-samples", type=int, default=None, help="最多读取多少条 prompt, 便于 probe。")
    parser.add_argument("--require-cuda", action="store_true", help="要求 CUDA, 正式 baseline 推荐启用。")
    return parser


def _require_file(path: Path, *, label: str) -> None:
    """检查必需输入文件是否存在, 失败时给出明确路径。"""

    if not path.is_file():
        raise FileNotFoundError(f"{label} 不存在: {path}")


def build_plan(
    *,
    repo_root: Path,
    prompt_plan: Path,
    observation_output: Path,
    artifact_root: Path,
    working_directory: Path,
    timeout_seconds: int,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """构造单条 Tree-Ring adapter baseline plan。

    通用工程写法:
    - plan 中保存显式 argv 列表, 避免 shell 字符串拼接。
    - 所有路径在写入 plan 前转为绝对路径, 便于 Colab 打包和复核。

    项目特定写法:
    - baseline_id 固定为 `tree_ring`, 与 CEG baseline registry 保持一致。
    - adapter 位于 `external_baselines/main_table/tree_ring_watermark/adapter`,
      不进入 `main/methods/ceg/` 方法层。
    """

    adapter_path = repo_root / "external_baselines" / "main_table" / "tree_ring_watermark" / "adapter" / "run_ceg_eval.py"
    _require_file(adapter_path, label="Tree-Ring adapter")
    _require_file(prompt_plan, label="CEG prompt plan")

    command = [
        sys.executable,
        str(adapter_path.resolve()),
        "--prompt-plan",
        str(prompt_plan.resolve()),
        "--out",
        str(observation_output.resolve()),
        "--artifact-root",
        str(artifact_root.resolve()),
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
        "--watermark-seed",
        str(args.watermark_seed),
        "--w-channel",
        str(args.w_channel),
        "--w-radius",
        str(args.w_radius),
        "--w-pattern",
        str(args.w_pattern),
    ]
    if args.threshold is not None:
        command.extend(["--threshold", str(args.threshold)])
    if str(args.attack_families).strip():
        command.extend(["--attack-families", str(args.attack_families)])
    if args.max_samples is not None:
        command.extend(["--max-samples", str(args.max_samples)])
    if args.require_cuda:
        command.append("--require-cuda")

    return [
        {
            "baseline_id": "tree_ring",
            "command": command,
            "output_path": str(observation_output.resolve()),
            "working_directory": str(working_directory.resolve()),
            "timeout_seconds": int(timeout_seconds),
        }
    ]


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    prompt_plan = Path(args.prompt_plan).resolve()
    observation_output = Path(args.observation_output).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    working_directory = Path(args.working_directory).resolve() if args.working_directory else repo_root

    plan = build_plan(
        repo_root=repo_root,
        prompt_plan=prompt_plan,
        observation_output=observation_output,
        artifact_root=artifact_root,
        working_directory=working_directory,
        timeout_seconds=args.timeout_seconds,
        args=args,
    )
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    observation_output.parent.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_path": str(output_path), "row_count": len(plan)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
