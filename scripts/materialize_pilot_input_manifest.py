"""把已提供的 pilot 产物物化为统一输入目录并生成 pilot_input_manifest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot_input_materializer import materialize_pilot_input_bundle


def build_parser() -> argparse.ArgumentParser:
    """构造 pilot 输入物化命令行参数."""
    parser = argparse.ArgumentParser(description="物化 CEG pilot 输入 bundle 并生成 pilot_input_manifest.json.")
    parser.add_argument("--out", required=True, help="pilot 输入 bundle 输出目录.")
    parser.add_argument("--run-id", default=None, help="可选运行标识, 写入物化 manifest.")
    parser.add_argument("--events", default=None, help="detection events 或统一 event records 输入.")
    parser.add_argument("--thresholds", default=None, help="thresholds JSON 输入.")
    parser.add_argument("--baseline-observations", default=None)
    parser.add_argument("--baseline-execution-manifest", default=None)
    parser.add_argument("--metric-rows", default=None)
    parser.add_argument("--metric-execution-manifest", default=None)
    parser.add_argument("--detection-execution-manifest", default=None)
    parser.add_argument("--image-pairs", default=None)
    parser.add_argument("--attacked-image-manifest", default=None)
    parser.add_argument("--attack-shard-manifest", default=None)
    parser.add_argument("--experiment-matrix", default=None)
    parser.add_argument("--readiness-requirements", default=None)
    parser.add_argument("--detection-output-root", default=None)
    parser.add_argument("--require-pass", action="store_true", help="物化或 preflight 未通过时返回非零退出码.")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    manifest = materialize_pilot_input_bundle(
        args.out,
        events=args.events,
        thresholds=args.thresholds,
        baseline_observations=args.baseline_observations,
        baseline_execution_manifest=args.baseline_execution_manifest,
        metric_rows=args.metric_rows,
        metric_execution_manifest=args.metric_execution_manifest,
        detection_execution_manifest=args.detection_execution_manifest,
        image_pairs=args.image_pairs,
        attacked_image_manifest=args.attacked_image_manifest,
        attack_shard_manifest=args.attack_shard_manifest,
        experiment_matrix=args.experiment_matrix,
        readiness_requirements=args.readiness_requirements,
        detection_output_root=args.detection_output_root,
        run_id=args.run_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.require_pass and manifest["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
