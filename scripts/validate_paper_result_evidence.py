"""校验论文结果包是否具备正式实验证据完整性的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.paper_result_evidence import validate_paper_result_evidence


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验论文结果目录、结果包或 Colab bundle 的正式实验证据完整性。")
    parser.add_argument("--target", required=True, help="paper_outputs、paper_results_package 或 colab_run_bundle 路径。")
    parser.add_argument("--out", default=None, help="可选 JSON 报告输出路径。")
    parser.add_argument(
        "--allow-dry-run",
        action="store_true",
        help="允许 dry-run 标记存在。该选项只应用于链路调试, 不应用于正式论文结果验收。",
    )
    parser.add_argument(
        "--allow-missing-experiment-coverage",
        action="store_true",
        help="不要求 paper_experiment_coverage_report.json 通过。该选项只应用于 pilot 或调试输出。",
    )
    parser.add_argument(
        "--require-external-command-results",
        action="store_true",
        help="要求 Colab bundle 中存在且通过外部 baseline 与高级指标命令结果。",
    )
    parser.add_argument(
        "--minimum-quality-metric-coverage",
        type=float,
        default=1.0,
        help="每个必需方法的 PSNR/SSIM/LPIPS/FID/CLIP score 最小覆盖率。",
    )
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="如果证据完整性未通过, 使用非零退出码阻断流水线。",
    )
    return parser


def main() -> None:
    """CLI 入口, 输出结构化 JSON 报告。"""
    parser = build_parser()
    args = parser.parse_args()
    report = validate_paper_result_evidence(
        args.target,
        allow_dry_run=args.allow_dry_run,
        require_experiment_coverage=not args.allow_missing_experiment_coverage,
        require_external_command_results=args.require_external_command_results,
        minimum_quality_metric_coverage=args.minimum_quality_metric_coverage,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.require_pass and report.get("overall_decision") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
