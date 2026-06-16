"""从分散的已提供 pilot 输入一键物化、构建并可选归档结果包."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.core.digest import build_stable_digest
from experiments.pilot_input_materializer import materialize_pilot_input_bundle
from experiments.external_result_evidence import validate_external_result_evidence


def _optional_path(value: str | None) -> str | None:
    """将空路径规范为 None, 便于 CLI 可选参数复用."""
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选参数存在时追加到子命令."""
    if _optional_path(value) is not None:
        command.extend([flag, str(value)])


def _run_command(command: list[str]) -> dict[str, object]:
    """执行子命令并返回可写入 manifest 的摘要."""
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def build_parser() -> argparse.ArgumentParser:
    """构造分散输入到论文结果包的一键命令行参数."""
    parser = argparse.ArgumentParser(description="从分散 pilot 输入一键生成 paper_results_package 并可选归档到 Drive.")
    parser.add_argument("--materialized-input-root", required=True, help="保存 canonical pilot 输入 bundle 的目录.")
    parser.add_argument("--out", required=True, help="pilot package 构建根目录.")
    parser.add_argument("--run-id", default=None, help="可选运行标识, 同时用于物化和归档.")
    parser.add_argument("--profile", default="paper_main_probe")
    parser.add_argument("--events", default=None)
    parser.add_argument("--thresholds", default=None)
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
    parser.add_argument("--require-paper-readiness", action="store_true")
    parser.add_argument("--allow-incomplete-package", action="store_true")
    parser.add_argument("--drive-root", default=None, help="可选 Drive 归档根目录.")
    parser.add_argument("--allow-invalid-archive-package", action="store_true")
    parser.add_argument(
        "--check-external-result-evidence",
        action="store_true",
        help="在构建结果包前校验外部 baseline 与高级 metric 的 execution manifest 证据.",
    )
    parser.add_argument(
        "--require-formal-external-result-claim",
        action="store_true",
        help="要求外部 baseline 与高级 metric manifest 声明 formal_result_claim 并提供 evidence_paths.",
    )
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)

    materialization = materialize_pilot_input_bundle(
        args.materialized_input_root,
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
    if materialization["overall_decision"] != "pass":
        summary = {
            "artifact_name": "pilot_raw_input_package_build_manifest.json",
            "overall_decision": "fail",
            "failed_step": "materialize_pilot_input",
            "materialization": materialization,
        }
        (output_root / "pilot_raw_input_package_build_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    external_result_evidence_report = None
    should_check_external_evidence = args.check_external_result_evidence or args.require_formal_external_result_claim
    if should_check_external_evidence:
        materialized_root = Path(args.materialized_input_root)
        external_result_evidence_report = validate_external_result_evidence(
            baseline_execution_manifest=materialized_root / "external_baselines" / "baseline_execution_manifest.json",
            metric_execution_manifest=materialized_root / "external_metrics" / "metric_execution_manifest.json",
            require_formal_claim=args.require_formal_external_result_claim,
        )
        (output_root / "external_result_evidence_report.json").write_text(
            json.dumps(external_result_evidence_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if external_result_evidence_report["overall_decision"] != "pass":
            summary = {
                "artifact_name": "pilot_raw_input_package_build_manifest.json",
                "overall_decision": "fail",
                "failed_step": "external_result_evidence_preflight",
                "materialization": materialization,
                "external_result_evidence_report": external_result_evidence_report,
            }
            (output_root / "pilot_raw_input_package_build_manifest.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            raise SystemExit(1)

    build_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_pilot_package_from_provided_results.py"),
        "--pilot-input-manifest",
        str(Path(args.materialized_input_root) / "pilot_input_manifest.json"),
        "--out",
        str(output_root),
        "--profile",
        str(args.profile),
    ]
    if args.require_paper_readiness:
        build_command.append("--require-paper-readiness")
    if args.allow_incomplete_package:
        build_command.append("--allow-incomplete-package")
    _append_optional(build_command, "--drive-root", args.drive_root)
    _append_optional(build_command, "--run-id", args.run_id)
    if args.allow_invalid_archive_package:
        build_command.append("--allow-invalid-archive-package")

    build_result = _run_command(build_command)
    if build_result["return_code"] != 0:
        summary = {
            "artifact_name": "pilot_raw_input_package_build_manifest.json",
            "overall_decision": "fail",
            "failed_step": "build_pilot_package_from_materialized_input",
            "materialization": materialization,
            "external_result_evidence_report": external_result_evidence_report,
            "build_result": build_result,
        }
        (output_root / "pilot_raw_input_package_build_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(int(build_result["return_code"]))

    summary = {
        "artifact_name": "pilot_raw_input_package_build_manifest.json",
        "overall_decision": "pass",
        "materialized_input_root": str(args.materialized_input_root),
        "pilot_input_manifest": str(Path(args.materialized_input_root) / "pilot_input_manifest.json"),
        "pilot_package_root": str(output_root),
        "run_id": _optional_path(args.run_id),
        "drive_root": _optional_path(args.drive_root),
        "materialization": materialization,
        "external_result_evidence_report": external_result_evidence_report,
        "build_result": build_result,
        "execution_digest": build_stable_digest(
            {
                "materialization_digest": materialization.get("materialization_digest"),
                "external_result_evidence_digest": (external_result_evidence_report or {}).get("evidence_digest"),
                "build_command": build_command,
                "run_id": args.run_id,
            }
        ),
    }
    (output_root / "pilot_raw_input_package_build_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
