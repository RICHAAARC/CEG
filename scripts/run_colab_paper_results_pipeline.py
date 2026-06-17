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
    parser.add_argument("--affine-rotation-degrees", default="-6,-3,0,3,6")
    parser.add_argument("--affine-scales", default="0.95,1.0,1.05")
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
        "--affine-rotation-degrees",
        str(args.affine_rotation_degrees),
        "--affine-scales",
        str(args.affine_scales),
    ]
    _append_optional(detection_command, "--attestation-key-env", args.attestation_key_env)
    _append_optional(detection_command, "--attestation-key-id", args.attestation_key_id)
    detection_result = _run_command(detection_command)
    if detection_result["return_code"] != 0:
        _fail(
            output_root,
            failed_step="run_ceg_detection_producer",
            results={"attack_result": attack_result, "detection_result": detection_result},
        )
        raise SystemExit(int(detection_result["return_code"]))

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
                "package_result": package_result,
                "archive_result": archive_result,
            },
        )
        raise SystemExit(int(archive_result["return_code"]))

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
        "package_run_root": str(package_run_root),
        "paper_results_package_root": str(package_run_root / "paper_results_package"),
        "drive_root": str(Path(args.drive_root).resolve()),
        "attack_result": attack_result,
        "detection_result": detection_result,
        "package_result": package_result,
        "archive_result": archive_result,
        "stage_summary_result": stage_summary_result,
        "execution_digest": build_stable_digest(
            {
                "attack_command": attack_command,
                "detection_command": detection_command,
                "package_command": package_command,
                "archive_command": archive_command,
            }
        ),
    }
    _write_manifest(output_root / PIPELINE_MANIFEST_NAME, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
