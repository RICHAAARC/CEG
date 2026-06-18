"""生成 T2SMark adapter 的 CEG 外部 baseline 命令计划。

该脚本只负责把已经存在的 T2SMark `results.json` 和 CEG `image_pairs.json`
组织成 `scripts/run_baseline_plan.py` 可执行的显式 argv 计划。它不运行
T2SMark 算法本体, 也不生成或伪造第三方 baseline 结果。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="生成 T2SMark adapter baseline plan。")
    parser.add_argument("--repo-root", required=True, help="CEG 仓库根目录。")
    parser.add_argument("--image-pairs", required=True, help="CEG image_pairs.json 路径。")
    parser.add_argument("--t2smark-results", required=True, help="T2SMark 已产生的 results.json 路径。")
    parser.add_argument("--out", required=True, help="输出 baseline plan JSON 路径。")
    parser.add_argument(
        "--observation-output",
        required=True,
        help="T2SMark adapter 应写出的 observation JSON 路径。",
    )
    parser.add_argument(
        "--working-directory",
        default=None,
        help="执行 adapter 命令时使用的工作目录。缺省时使用 repo-root。",
    )
    parser.add_argument("--timeout-seconds", type=int, default=7200, help="adapter 命令超时时间。")
    parser.add_argument("--threshold", type=float, default=None, help="可选显式检测阈值。")
    parser.add_argument("--attack-family", default="clean", help="无 attack manifest 时使用的攻击族标签。")
    parser.add_argument("--attack-condition", default="clean_none", help="无 attack manifest 时使用的攻击条件标签。")
    parser.add_argument(
        "--attacked-image-manifest",
        default=None,
        help="可选 attacked_image_manifest.json, 用于补充攻击样本 observation。",
    )
    return parser


def _require_file(path: Path, *, label: str) -> None:
    """检查必需输入文件是否存在, 失败时给出明确路径。"""

    if not path.is_file():
        raise FileNotFoundError(f"{label} 不存在: {path}")


def build_plan(
    *,
    repo_root: Path,
    image_pairs: Path,
    t2smark_results: Path,
    observation_output: Path,
    working_directory: Path,
    timeout_seconds: int,
    threshold: float | None,
    attack_family: str,
    attack_condition: str,
    attacked_image_manifest: Path | None,
) -> list[dict[str, Any]]:
    """构造单条 T2SMark adapter baseline plan。

    通用工程写法:
    - plan 中保存显式 argv 列表, 避免 shell 字符串拼接。
    - 所有路径在写入 plan 前转为绝对路径, 便于 Colab 归档后复核。

    项目特定写法:
    - baseline_id 固定为 `t2smark`, 与 CEG baseline registry 保持一致。
    - adapter 位于 `external_baselines/main_table/t2smark/adapter`, 不进入 `main/` 方法层。
    """

    adapter_path = repo_root / "external_baselines" / "main_table" / "t2smark" / "adapter" / "run_ceg_eval.py"
    _require_file(adapter_path, label="T2SMark adapter")
    _require_file(image_pairs, label="CEG image_pairs.json")
    _require_file(t2smark_results, label="T2SMark results.json")
    if attacked_image_manifest is not None:
        _require_file(attacked_image_manifest, label="attacked_image_manifest.json")

    command = [
        sys.executable,
        str(adapter_path.resolve()),
        "--image-pairs",
        str(image_pairs.resolve()),
        "--t2smark-results",
        str(t2smark_results.resolve()),
        "--out",
        str(observation_output.resolve()),
        "--attack-family",
        attack_family,
        "--attack-condition",
        attack_condition,
    ]
    if threshold is not None:
        command.extend(["--threshold", str(threshold)])
    if attacked_image_manifest is not None:
        command.extend(["--attacked-image-manifest", str(attacked_image_manifest.resolve())])

    return [
        {
            "baseline_id": "t2smark",
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
    image_pairs = Path(args.image_pairs).resolve()
    t2smark_results = Path(args.t2smark_results).resolve()
    observation_output = Path(args.observation_output).resolve()
    working_directory = Path(args.working_directory).resolve() if args.working_directory else repo_root
    attacked_image_manifest = Path(args.attacked_image_manifest).resolve() if args.attacked_image_manifest else None

    plan = build_plan(
        repo_root=repo_root,
        image_pairs=image_pairs,
        t2smark_results=t2smark_results,
        observation_output=observation_output,
        working_directory=working_directory,
        timeout_seconds=args.timeout_seconds,
        threshold=args.threshold,
        attack_family=args.attack_family,
        attack_condition=args.attack_condition,
        attacked_image_manifest=attacked_image_manifest,
    )
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    observation_output.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_path": str(output_path), "row_count": len(plan)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
