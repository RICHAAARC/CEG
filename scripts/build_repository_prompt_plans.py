"""从仓库内置 prompt 文本构造论文运行 prompt plan。

该脚本的作用是把人工整理好的纯文本 prompt 列表转换为 Colab 图像生成后端可直接读取的
JSON prompt plan。通用工程写法是保留原始文本源文件, 再用可重复脚本生成结构化计划文件。
项目特定写法是固定产出 paper_main_probe、paper_main_pilot 和 paper_main_full 三个论文运行 profile,
并显式记录 calibration / test split, 使后续 TPR@FPR 统计可以追溯阈值校准集合和测试集合。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "prompts" / "sources"
DEFAULT_OUTPUT_DIR = ROOT / "prompts" / "prompt_plans"

SD_MODEL_ID = "stabilityai/stable-diffusion-3.5-medium"
WATERMARK_BACKEND = "ceg_content_chain_embedding"

PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "paper_main_probe": {
        "source_file": "paper_main_pilot_prompts.txt",
        "prompt_count": 10,
        "calibration_count": 5,
        "target_fpr": 0.01,
        "purpose": "端到端流程探针运行, 使用 5 个 calibration 和 5 个 test 样本确认 Colab、SD 生成、水印、攻击、检测和 TPR@FPR 统计链路可闭环。",
    },
    "paper_main_pilot": {
        "source_file": "paper_main_pilot_prompts.txt",
        "prompt_count": 600,
        "calibration_count": 300,
        "target_fpr": 0.01,
        "purpose": "论文主线试运行, 用于支持 TPR@FPR=0.01 的校准集合和测试集合拆分。",
    },
    "paper_main_full": {
        "source_file": "paper_main_full_prompts.txt",
        "prompt_count": 6000,
        "calibration_count": 3000,
        "target_fpr": 0.001,
        "purpose": "论文主结果正式运行, 用于支持 TPR@FPR=0.001 的校准集合和测试集合拆分。",
    },
}


def _read_prompt_lines(path: Path) -> list[str]:
    """读取非空 prompt 行, 保留原始顺序作为可复现实验顺序。"""

    lines = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"prompt source is empty: {path}")
    return lines


def _stable_seed(profile: str, index: int, prompt_text: str) -> int:
    """根据 profile、行号和 prompt 文本生成稳定 seed, 避免不同机器上出现不可追溯的采样差异。"""

    payload = f"{profile}\n{index}\n{prompt_text}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:8], 16)


def _build_rows(profile: str, prompts: list[str], *, calibration_count: int, source_file: str) -> list[dict[str, Any]]:
    """构造图像生成后端需要的逐样本记录。"""

    rows: list[dict[str, Any]] = []
    for zero_index, prompt_text in enumerate(prompts):
        one_index = zero_index + 1
        split = "calibration" if zero_index < calibration_count else "test"
        rows.append(
            {
                "profile": profile,
                "prompt_id": f"{profile}_prompt_{one_index:06d}",
                "image_id": f"{profile}_image_{one_index:06d}",
                "sample_index": one_index,
                "source_file": source_file,
                "source_line_number": one_index,
                "split": split,
                "prompt_text": prompt_text,
                "seed": _stable_seed(profile, one_index, prompt_text),
                "sd_model_id": SD_MODEL_ID,
                "watermark_backend": WATERMARK_BACKEND,
            }
        )
    return rows


def _write_json(path: Path, payload: Any) -> None:
    """写出 UTF-8 JSON, 供 notebook、脚本和审计流程直接复用。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    """把仓库内路径写成相对路径, 仓库外临时路径保留绝对路径。"""

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_prompt_plan(profile: str, *, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict[str, Any]:
    """为单个 profile 构造 prompt plan 对象。"""

    if profile not in PROFILE_SPECS:
        raise ValueError(f"unknown prompt plan profile: {profile}")
    spec = PROFILE_SPECS[profile]
    source_file = str(spec["source_file"])
    source_path = source_dir / source_file
    all_prompts = _read_prompt_lines(source_path)
    prompt_count = int(spec["prompt_count"])
    if len(all_prompts) < prompt_count:
        raise ValueError(f"{source_path} has {len(all_prompts)} prompts, but {profile} requires {prompt_count}")
    selected_prompts = all_prompts[:prompt_count]
    rows = _build_rows(profile, selected_prompts, calibration_count=int(spec["calibration_count"]), source_file=source_file)
    split_counts: dict[str, int] = {}
    for row in rows:
        split = str(row["split"])
        split_counts[split] = split_counts.get(split, 0) + 1
    return {
        "schema_version": "ceg_prompt_plan_v1",
        "profile": profile,
        "purpose": spec["purpose"],
        "source": {
            "source_file": source_file,
            "source_path": _display_path(source_path),
            "source_prompt_count": len(all_prompts),
            "selected_prompt_count": len(rows),
        },
        "generation_defaults": {
            "sd_model_id": SD_MODEL_ID,
            "watermark_backend": WATERMARK_BACKEND,
            "target_fpr": float(spec["target_fpr"]),
        },
        "split_policy": {
            "calibration_count": int(spec["calibration_count"]),
            "test_count": split_counts.get("test", 0),
            "split_counts": split_counts,
        },
        "prompts": rows,
    }


def build_all_prompt_plans(*, source_dir: Path = DEFAULT_SOURCE_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    """构造全部论文运行 prompt plan, 并写出汇总 manifest。"""

    manifest: dict[str, Any] = {
        "schema_version": "ceg_prompt_plan_manifest_v1",
        "profiles": {},
    }
    for profile in PROFILE_SPECS:
        plan = build_prompt_plan(profile, source_dir=source_dir)
        output_path = output_dir / f"{profile}_prompt_plan.json"
        _write_json(output_path, plan)
        manifest["profiles"][profile] = {
            "prompt_plan_path": _display_path(output_path),
            "prompt_count": len(plan["prompts"]),
            "split_counts": plan["split_policy"]["split_counts"],
            "target_fpr": plan["generation_defaults"]["target_fpr"],
            "sd_model_id": plan["generation_defaults"]["sd_model_id"],
            "watermark_backend": plan["generation_defaults"]["watermark_backend"],
        }
    manifest_path = output_dir / "prompt_plan_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="从仓库内置 prompt 文本构造 CEG 论文运行 prompt plan。")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="prompt 文本源目录。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="prompt plan 输出目录。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    manifest = build_all_prompt_plans(source_dir=Path(args.source_dir), output_dir=Path(args.output_dir))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

