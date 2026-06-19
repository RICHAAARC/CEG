"""生成补充表图像水印 baseline adapter 命令计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ADAPTERS = {
    "rivagan_invisible_watermark": "external_baselines/supplementary_table/rivagan_invisible_watermark/adapter/run_ceg_eval.py",
    "wam": "external_baselines/supplementary_table/watermark_anything/adapter/run_ceg_eval.py",
    "trustmark": "external_baselines/supplementary_table/trustmark/adapter/run_ceg_eval.py",
}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成补充表图像水印 baseline adapter plan。")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--methods", default="rivagan_invisible_watermark,wam,trustmark")
    parser.add_argument("--image-pairs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--working-directory", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=86400)
    parser.add_argument("--attack-families", default="")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--rivagan-payload", default="CEG0")
    parser.add_argument("--wam-checkpoint", default=None)
    parser.add_argument("--trustmark-payload", default="cegmark")
    parser.add_argument("--trustmark-model-type", default="Q", choices=["C", "Q", "B", "P"])
    return parser

def _selected_methods(value: str) -> list[str]:
    methods = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in methods if item not in ADAPTERS]
    if unknown:
        raise ValueError(f"不支持的补充表 image watermark baseline: {unknown}")
    return methods

def _extend_method_args(command: list[str], method_id: str, args: argparse.Namespace) -> None:
    if method_id == "rivagan_invisible_watermark":
        command.extend(["--payload", str(args.rivagan_payload)])
    elif method_id == "wam" and args.wam_checkpoint:
        command.extend(["--checkpoint", str(Path(args.wam_checkpoint).resolve())])
    elif method_id == "trustmark":
        command.extend(["--payload", str(args.trustmark_payload), "--model-type", str(args.trustmark_model_type)])

def build_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    repo_root = Path(args.repo_root).resolve()
    image_pairs = Path(args.image_pairs).resolve()
    output_root = Path(args.output_root).resolve()
    working_directory = Path(args.working_directory).resolve() if args.working_directory else repo_root
    if not image_pairs.is_file():
        raise FileNotFoundError(f"image_pairs 不存在: {image_pairs}")
    rows: list[dict[str, Any]] = []
    for method_id in _selected_methods(args.methods):
        adapter_path = repo_root / ADAPTERS[method_id]
        if not adapter_path.is_file():
            raise FileNotFoundError(f"{method_id} adapter 不存在: {adapter_path}")
        method_root = output_root / method_id
        observation_output = method_root / "baseline_observations.json"
        artifact_root = method_root / "artifacts"
        command = [sys.executable, str(adapter_path), "--image-pairs", str(image_pairs), "--out", str(observation_output), "--artifact-root", str(artifact_root)]
        if str(args.attack_families).strip():
            command.extend(["--attack-families", str(args.attack_families)])
        if args.max_samples is not None:
            command.extend(["--max-samples", str(args.max_samples)])
        if args.threshold is not None:
            command.extend(["--threshold", str(args.threshold)])
        _extend_method_args(command, method_id, args)
        rows.append({"baseline_id": method_id, "command": command, "output_path": str(observation_output), "working_directory": str(working_directory), "timeout_seconds": int(args.timeout_seconds)})
    return rows

def main() -> None:
    args = build_parser().parse_args()
    plan = build_plan(args)
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_root).resolve().mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_path": str(output_path), "row_count": len(plan), "methods": [row["baseline_id"] for row in plan]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
