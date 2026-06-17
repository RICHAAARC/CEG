"""校验 Colab 端到端运行是否满足指定正式运行规格。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.formal_run_spec import validate_formal_run_against_spec  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="校验 CEG 正式运行规格。")
    parser.add_argument("--manifest", required=True, help="colab_end_to_end_paper_pipeline_manifest.json 路径。")
    parser.add_argument("--profile", required=True, help="formal run profile, 如 paper_main_probe / paper_main_full。")
    parser.add_argument("--spec", default="configs/formal_run_specs.json", help="formal_run_specs.json 路径。")
    parser.add_argument("--out", required=True, help="规格校验报告输出路径。")
    parser.add_argument("--allow-existing-image-generation", action="store_true", help="允许复核断点续跑产物。")
    parser.add_argument("--require-pass", action="store_true", help="规格校验失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise TypeError(f"end-to-end manifest must be object: {manifest_path}")
    report = validate_formal_run_against_spec(
        end_to_end_manifest=manifest,
        profile=args.profile,
        spec_path=args.spec,
        allow_existing_image_generation=args.allow_existing_image_generation,
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
