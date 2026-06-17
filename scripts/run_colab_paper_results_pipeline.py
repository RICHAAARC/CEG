"""运行 Colab 论文结果包流水线。

该脚本属于实验编排层, 不实现 CEG 方法本身。它假设图像生成阶段已经在 Google Drive 工作区内
产出 `inputs/images/image_pairs.json`, 然后顺序执行 attack、真实 CEG detection、fixed-FPR 校准、
paper outputs、paper results package 和 Drive archive。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.core.digest import build_stable_digest
from main.watermarking.semantic_mask import GRADIENT_SALIENCY_BACKEND_ID, INSPYRENET_BACKEND_ID


PIPELINE_MANIFEST_NAME = "colab_paper_results_pipeline_manifest.json"


def _run_command(command: list[str]) -> dict[str, Any]:
    """执行子命令并返回可审计摘要。"""

    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """写出流水线 manifest。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选参数存在时追加到命令。"""

    if value is not None and str(value).strip() != "":
        command.extend([flag, str(value)])


def _fail(output_root: Path, *, failed_step: str, results: dict[str, Any]) -> None:
    """写出失败 manifest 并停止。"""

    manifest = {
        "artifact_name": PIPELINE_MANIFEST_NAME,
        "overall_decision": "fail",
        "failed_step": failed_step,
        **results,
    }
    _write_manifest(output_root / PIPELINE_MANIFEST_NAME, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 CEG Colab 论文结果包流水线。")
    parser.add_argument("--workspace", required=True, help="Google Drive 中的 CEG pilot workspace。")
    parser.add_argument("--drive-root", default="/content/drive/MyDrive/CEG", help="Drive CEG 根目录。")
    parser.add_argument("--run-id", default=None, help="可选归档运行 ID。")
    parser.add_argument("--image-pairs", default=None, help="可选 image_pairs.json 路径, 默认读取 workspace/inputs/images/image_pairs.json。")
    parser.add_argument("--out", default=None, help="可选流水线输出目录, 默认写入 workspace/paper_results_pipeline。")
    parser.add_argument("--attack-families", default="brightness_contrast,gaussian_noise,rotate,resize,jpeg")
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--profile", default="paper_main_probe")
    parser.add_argument("--allow-incomplete-package", action="store_true")
    parser.add_argument("--allow-invalid-archive", action="store_true")
    parser.add_argument("--attestation-key-env", default=None)
    parser.add_argument("--attestation-key-id", default=None)
    parser.add_argument("--detection-formal-result-claim", action="store_true", help="当 detection backend readiness 通过时声明正式方法结果。")
    parser.add_argument("--semantic-mask-backend", default=GRADIENT_SALIENCY_BACKEND_ID, choices=[GRADIENT_SALIENCY_BACKEND_ID, INSPYRENET_BACKEND_ID], help="detection 使用的 semantic mask backend。")
    parser.add_argument("--affine-rotation-degrees", default="-6,-3,0,3,6")
    parser.add_argument("--affine-scales", default="0.95,1.0,1.05")
    parser.add_argument("--perspective-offsets", default="0.0")
    parser.add_argument("--feature-homography-enabled", default="true")
    parser.add_argument("--local-deformation-enabled", default="true")
    parser.add_argument("--baseline-plan", default=None, help="可选外部 baseline 命令计划。")
    parser.add_argument("--baseline-observations", default=None, help="可选已生成的 baseline observations 文件。")
    parser.add_argument("--baseline-execution-manifest", default=None, help="可选已生成的 baseline execution manifest。")
    parser.add_argument("--baseline-formal-result-claim", action="store_true", help="导入离线 baseline 时声明其有正式证据。")
    parser.add_argument("--baseline-evidence-path", action="append", default=[], help="离线 baseline 正式证据路径。")
    parser.add_argument("--refresh-stage-summary", action="store_true")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    workspace = Path(args.workspace).resolve()
    output_root = Path(args.out).resolve() if args.out else workspace / "paper_results_pipeline"
    output_root.mkdir(parents=True, exist_ok=True)
    image_pairs = Path(args.image_pairs).resolve() if args.image_pairs else workspace / "inputs" / "images" / "image_pairs.json"
    if not image_pairs.is_file():
        raise FileNotFoundError(f"image_pairs.json missing: {image_pairs}")

    attack_root = output_root / "attack_outputs"
    detection_root = output_root / "detection_outputs"
    baseline_root = output_root / "baseline_outputs"
    metric_root = output_root / "metric_outputs"
    package_run_root = output_root / "calibrated_paper_results_package"

    attack_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_image_attack_workflow.py"),
        "--image-pairs",
        str(image_pairs),
        "--out",
        str(attack_root),
        "--attack-families",
        str(args.attack_families),
    ]
    attack_result = _run_command(attack_command)
    if attack_result["return_code"] != 0:
        _fail(output_root, failed_step="run_image_attack_workflow", results={"attack_result": attack_result})
        raise SystemExit(int(attack_result["return_code"]))

    attacked_manifest = attack_root / "image_manifests" / "attacked_image_manifest.json"
    attack_shard_manifest = attack_root / "image_manifests" / "attack_shard_manifest.json"
    detection_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_ceg_detection_producer.py"),
        "--image-pairs",
        str(image_pairs),
        "--attacked-image-manifest",
        str(attacked_manifest),
        "--out",
        str(detection_root),
        "--detection-backend",
        "ceg_content_chain_detection",
        "--semantic-mask-backend",
        str(args.semantic_mask_backend),
        "--affine-rotation-degrees",
        str(args.affine_rotation_degrees),
        "--affine-scales",
        str(args.affine_scales),
        "--perspective-offsets",
        str(args.perspective_offsets),
        "--feature-homography-enabled",
        str(args.feature_homography_enabled),
        "--local-deformation-enabled",
        str(args.local_deformation_enabled),
    ]
    _append_optional(detection_command, "--attestation-key-env", args.attestation_key_env)
    _append_optional(detection_command, "--attestation-key-id", args.attestation_key_id)
    if args.detection_formal_result_claim:
        detection_command.append("--formal-result-claim")
    detection_result = _run_command(detection_command)
    if detection_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="run_ceg_detection_producer",
            results={"attack_result": attack_result, "detection_result": detection_result},
        )
        raise SystemExit(int(detection_result["return_code"]))

    baseline_result = None
    baseline_observations_path = args.baseline_observations
    baseline_execution_manifest_path = args.baseline_execution_manifest
    if args.baseline_plan and args.baseline_observations:
        raise ValueError("--baseline-plan and --baseline-observations are mutually exclusive")
    if args.baseline_plan:
        baseline_command = [
            sys.executable,
            str(ROOT / "scripts" / "run_baseline_plan.py"),
            "--plan",
            str(Path(args.baseline_plan).resolve()),
            "--out",
            str(baseline_root),
            "--require-pass",
        ]
        if args.baseline_formal_result_claim:
            baseline_command.append("--formal-result-claim")
        for evidence_path in args.baseline_evidence_path:
            baseline_command.extend(["--evidence-path", str(Path(evidence_path).resolve())])
        baseline_result = _run_command(baseline_command)
        if baseline_result["return_code"] != 0:
            _fail(
                output_root,
                failed_step="run_baseline_plan",
                results={
                    "attack_result": attack_result,
                    "detection_result": detection_result,
                    "baseline_result": baseline_result,
                },
            )
            raise SystemExit(int(baseline_result["return_code"]))
        baseline_observations_path = str(baseline_root / "baseline_observations.json")
        baseline_execution_manifest_path = str(baseline_root / "baseline_execution_manifest.json")
    elif args.baseline_observations:
        baseline_command = [
            sys.executable,
            str(ROOT / "scripts" / "import_baseline_observations.py"),
            "--observations",
            str(Path(args.baseline_observations).resolve()),
            "--out",
            str(baseline_root),
        ]
        if args.baseline_formal_result_claim:
            baseline_command.append("--formal-result-claim")
        for evidence_path in args.baseline_evidence_path:
            baseline_command.extend(["--evidence-path", str(Path(evidence_path).resolve())])
        baseline_result = _run_command(baseline_command)
        if baseline_result["return_code"] != 0:
            _fail(
                output_root,
                failed_step="import_baseline_observations",
                results={
                    "attack_result": attack_result,
                    "detection_result": detection_result,
                    "baseline_result": baseline_result,
                },
            )
            raise SystemExit(int(baseline_result["return_code"]))
        baseline_observations_path = str(baseline_root / "baseline_observations.json")
        baseline_execution_manifest_path = str(baseline_root / "baseline_execution_manifest.json")

    metric_rows_path = metric_root / "quality_metric_rows.json"
    metric_manifest_path = metric_root / "metric_execution_manifest.json"
    metric_command = [
        sys.executable,
        str(ROOT / "scripts" / "compute_image_quality_metrics.py"),
        "--pairs",
        str(image_pairs),
        "--out",
        str(metric_rows_path),
        "--manifest",
        str(metric_manifest_path),
        "--formal-result-claim",
    ]
    metric_result = _run_command(metric_command)
    if metric_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="compute_image_quality_metrics",
            results={
                "attack_result": attack_result,
                "detection_result": detection_result,
                "baseline_result": baseline_result,
                "metric_result": metric_result,
            },
        )
        raise SystemExit(int(metric_result["return_code"]))

    package_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_calibrated_paper_results_package.py"),
        "--detection-events",
        str(detection_root / "detection_events.json"),
        "--out",
        str(package_run_root),
        "--target-fpr",
        str(args.target_fpr),
        "--profile",
        str(args.profile),
        "--image-pairs",
        str(image_pairs),
        "--attacked-image-manifest",
        str(attacked_manifest),
        "--attack-shard-manifest",
        str(attack_shard_manifest),
    ]
    _append_optional(package_command, "--baseline-observations", baseline_observations_path)
    _append_optional(package_command, "--baseline-execution-manifest", baseline_execution_manifest_path)
    package_command.extend(["--metric-rows", str(metric_rows_path), "--metric-execution-manifest", str(metric_manifest_path)])
    if args.allow_incomplete_package:
        package_command.append("--allow-incomplete-package")
    package_result = _run_command(package_command)
    if package_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="build_calibrated_paper_results_package",
            results={
                "attack_result": attack_result,
                "detection_result": detection_result,
                "baseline_result": baseline_result,
                "metric_result": metric_result,
                "package_result": package_result,
            },
        )
        raise SystemExit(int(package_result["return_code"]))

    archive_command = [
        sys.executable,
        str(ROOT / "scripts" / "archive_paper_results_to_drive.py"),
        "--package-root",
        str(package_run_root / "paper_results_package"),
        "--drive-root",
        str(Path(args.drive_root).resolve()),
    ]
    _append_optional(archive_command, "--run-id", args.run_id or workspace.name)
    if args.allow_invalid_archive:
        archive_command.append("--allow-invalid-package")
    archive_result = _run_command(archive_command)
    if archive_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="archive_paper_results_to_drive",
            results={
                "attack_result": attack_result,
                "detection_result": detection_result,
                "baseline_result": baseline_result,
                "metric_result": metric_result,
                "package_result": package_result,
                "archive_result": archive_result,
            },
        )
        raise SystemExit(int(archive_result["return_code"]))

    effective_run_id = args.run_id or workspace.name
    drive_inventory_path = Path(args.drive_root).resolve() / "result_inventories" / f"drive_result_inventory_{effective_run_id}.json"
    drive_inventory_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_drive_result_inventory.py"),
        "--drive-root",
        str(Path(args.drive_root).resolve()),
        "--out",
        str(drive_inventory_path),
    ]
    drive_inventory_result = _run_command(drive_inventory_command)
    if drive_inventory_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="build_drive_result_inventory",
            results={
                "attack_result": attack_result,
                "detection_result": detection_result,
                "baseline_result": baseline_result,
                "metric_result": metric_result,
                "package_result": package_result,
                "archive_result": archive_result,
                "drive_inventory_result": drive_inventory_result,
            },
        )
        raise SystemExit(int(drive_inventory_result["return_code"]))

    stage_summary_result = None
    if args.refresh_stage_summary:
        summary_command = [sys.executable, str(ROOT / "scripts" / "build_pilot_stage_progress_summary.py"), "--workspace", str(workspace)]
        stage_summary_result = _run_command(summary_command)
        if stage_summary_result["return_code"] != 0:
            _fail(
                output_root,
                failed_step="build_pilot_stage_progress_summary",
                results={
                    "attack_result": attack_result,
                    "detection_result": detection_result,
                    "baseline_result": baseline_result,
                    "package_result": package_result,
                    "archive_result": archive_result,
                    "stage_summary_result": stage_summary_result,
                },
            )
            raise SystemExit(int(stage_summary_result["return_code"]))

    manifest = {
        "artifact_name": PIPELINE_MANIFEST_NAME,
        "overall_decision": "pass",
        "workspace": str(workspace),
        "image_pairs": str(image_pairs),
        "attack_root": str(attack_root),
        "attacked_image_manifest": str(attacked_manifest),
        "attack_shard_manifest": str(attack_shard_manifest),
        "detection_root": str(detection_root),
        "baseline_root": str(baseline_root) if baseline_result is not None else None,
        "baseline_observations_path": baseline_observations_path,
        "baseline_execution_manifest_path": baseline_execution_manifest_path,
        "metric_root": str(metric_root),
        "metric_rows_path": str(metric_rows_path),
        "metric_execution_manifest_path": str(metric_manifest_path),
        "package_run_root": str(package_run_root),
        "paper_results_package_root": str(package_run_root / "paper_results_package"),
        "drive_root": str(Path(args.drive_root).resolve()),
        "drive_result_inventory": str(drive_inventory_path),
        "attack_result": attack_result,
        "detection_result": detection_result,
        "baseline_result": baseline_result,
        "metric_result": metric_result,
        "package_result": package_result,
        "archive_result": archive_result,
        "stage_summary_result": stage_summary_result,
        "execution_digest": build_stable_digest(
            {
                "attack_command": attack_command,
                "detection_command": detection_command,
                "baseline_observations_path": baseline_observations_path,
                "baseline_execution_manifest_path": baseline_execution_manifest_path,
                "metric_command": metric_command,
                "package_command": package_command,
                "archive_command": archive_command,
                "drive_inventory_command": drive_inventory_command,
            }
        ),
    }
    _write_manifest(output_root / PIPELINE_MANIFEST_NAME, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
