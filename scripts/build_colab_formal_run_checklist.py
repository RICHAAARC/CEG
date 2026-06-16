"""生成 Colab 正式论文实验运行清单的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper_workflow.colab_utils.cold_start import write_colab_formal_run_checklist


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 Colab 正式实验从冷启动到论文结果的运行清单。")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--profile", default="paper_main_full")
    parser.add_argument("--use-dry-run-inputs", action="store_true")
    parser.add_argument("--run-external-plans", action="store_true")
    parser.add_argument(
        "--allow-missing-gpu-for-external-plans",
        action="store_true",
        help="允许正式外部 baseline / metric 计划在当前运行时未检测到 GPU 时通过预检。仅用于已确认第三方任务不需要 GPU 的场景。",
    )
    parser.add_argument("--allow-missing-experiment-coverage", action="store_true")
    parser.add_argument("--events", default=None)
    parser.add_argument("--thresholds", default=None)
    parser.add_argument("--sample-manifest", default=None)
    parser.add_argument("--compute-basic-image-metrics", action="store_true")
    parser.add_argument("--calibrate-thresholds", action="store_true")
    parser.add_argument("--threshold-target-fpr", type=float, default=0.01)
    parser.add_argument("--threshold-calibration-split", default="calibration")
    parser.add_argument("--baseline-observations", default=None)
    parser.add_argument("--metric-rows", default=None)
    parser.add_argument("--baseline-plan", default=None)
    parser.add_argument("--metric-plan", default=None)
    parser.add_argument("--baseline-root", default=None)
    parser.add_argument("--metric-root", default=None)
    parser.add_argument("--image-pairs", default=None)
    parser.add_argument("--reference-image-root", default=None)
    parser.add_argument("--generated-image-root", default=None)
    parser.add_argument("--image-prompt-rows", default=None)
    parser.add_argument("--require-pass", action="store_true", help="清单存在阻断项时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口, 写出正式 Colab 运行清单。"""
    parser = build_parser()
    args = parser.parse_args()
    checklist = write_colab_formal_run_checklist(
        args.out,
        args.repo_root,
        args.workspace_root,
        profile=args.profile,
        use_dry_run_inputs=args.use_dry_run_inputs,
        run_external_plans=args.run_external_plans,
        require_gpu_for_external_plans=not args.allow_missing_gpu_for_external_plans,
        require_experiment_coverage=not args.allow_missing_experiment_coverage,
        events_path=args.events,
        thresholds_path=args.thresholds,
        sample_manifest_path=args.sample_manifest,
        compute_basic_image_metrics=args.compute_basic_image_metrics,
        calibrate_thresholds=args.calibrate_thresholds,
        threshold_target_fpr=args.threshold_target_fpr,
        threshold_calibration_split=args.threshold_calibration_split,
        baseline_observations_path=args.baseline_observations,
        metric_rows_path=args.metric_rows,
        baseline_plan_path=args.baseline_plan,
        metric_plan_path=args.metric_plan,
        baseline_root=args.baseline_root,
        metric_root=args.metric_root,
        image_pairs_path=args.image_pairs,
        reference_image_root=args.reference_image_root,
        generated_image_root=args.generated_image_root,
        image_prompt_rows_path=args.image_prompt_rows,
    )
    print(json.dumps(checklist, ensure_ascii=False, indent=2))
    if args.require_pass and checklist.get("overall_decision") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
