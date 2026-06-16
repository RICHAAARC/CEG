"""从已提供的实验产物一键构建 pilot 论文结果包并可选归档到 Drive."""

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


def _optional_path(value: str | None) -> str | None:
    """把空字符串规范化为 None, 便于命令行可选参数复用."""
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选路径存在时追加命令行参数."""
    if _optional_path(value) is not None:
        command.extend([flag, str(value)])


def _run_command(command: list[str]) -> dict[str, object]:
    """执行子命令并返回可写入 manifest 的执行摘要."""
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def build_parser() -> argparse.ArgumentParser:
    """构造 pilot 结果包一键构建命令行参数."""
    parser = argparse.ArgumentParser(description="从已提供的 CEG pilot 产物构建并归档 paper_results_package.")
    parser.add_argument("--events", required=True, help="detection_events.json 或统一 event records 输入.")
    parser.add_argument("--thresholds", required=True, help="detection_thresholds.json 或 method threshold 映射.")
    parser.add_argument("--out", required=True, help="pilot package 构建根目录.")
    parser.add_argument("--profile", default="paper_main_probe")
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
    parser.add_argument("--require-paper-readiness", action="store_true")
    parser.add_argument("--allow-incomplete-package", action="store_true")
    parser.add_argument("--drive-root", default=None, help="可选 Drive 归档根目录.")
    parser.add_argument("--run-id", default=None, help="可选归档运行标识.")
    parser.add_argument("--allow-invalid-archive-package", action="store_true")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    output_root = Path(args.out)
    paper_outputs_root = output_root / "paper_outputs"
    package_root = output_root / "paper_results_package"
    output_root.mkdir(parents=True, exist_ok=True)

    build_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_paper_outputs.py"),
        "--events",
        str(args.events),
        "--thresholds",
        str(args.thresholds),
        "--profile",
        str(args.profile),
        "--out",
        str(paper_outputs_root),
    ]
    _append_optional(build_command, "--baseline-observations", args.baseline_observations)
    _append_optional(build_command, "--baseline-execution-manifest", args.baseline_execution_manifest)
    _append_optional(build_command, "--metric-rows", args.metric_rows)
    _append_optional(build_command, "--metric-execution-manifest", args.metric_execution_manifest)
    _append_optional(build_command, "--detection-execution-manifest", args.detection_execution_manifest)
    _append_optional(build_command, "--image-pairs", args.image_pairs)
    _append_optional(build_command, "--attacked-image-manifest", args.attacked_image_manifest)
    _append_optional(build_command, "--attack-shard-manifest", args.attack_shard_manifest)
    _append_optional(build_command, "--experiment-matrix", args.experiment_matrix)
    _append_optional(build_command, "--readiness-requirements", args.readiness_requirements)
    if args.require_paper_readiness:
        build_command.append("--require-paper-readiness")
    build_result = _run_command(build_command)
    if build_result["return_code"] != 0:
        summary = {
            "artifact_name": "pilot_package_build_manifest.json",
            "overall_decision": "fail",
            "failed_step": "build_paper_outputs",
            "build_result": build_result,
        }
        (output_root / "pilot_package_build_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(int(build_result["return_code"]))

    export_command = [
        sys.executable,
        str(ROOT / "scripts" / "export_paper_results_package.py"),
        "--source-output-root",
        str(paper_outputs_root),
        "--package-root",
        str(package_root),
    ]
    if args.allow_incomplete_package:
        export_command.append("--allow-incomplete")
    export_result = _run_command(export_command)
    if export_result["return_code"] != 0:
        summary = {
            "artifact_name": "pilot_package_build_manifest.json",
            "overall_decision": "fail",
            "failed_step": "export_paper_results_package",
            "build_result": build_result,
            "export_result": export_result,
        }
        (output_root / "pilot_package_build_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(int(export_result["return_code"]))

    archive_result = None
    if _optional_path(args.drive_root) is not None:
        archive_command = [
            sys.executable,
            str(ROOT / "scripts" / "archive_paper_results_to_drive.py"),
            "--package-root",
            str(package_root),
            "--drive-root",
            str(args.drive_root),
        ]
        _append_optional(archive_command, "--run-id", args.run_id)
        if args.allow_invalid_archive_package:
            archive_command.append("--allow-invalid-package")
        archive_result = _run_command(archive_command)
        if archive_result["return_code"] != 0:
            summary = {
                "artifact_name": "pilot_package_build_manifest.json",
                "overall_decision": "fail",
                "failed_step": "archive_paper_results_to_drive",
                "build_result": build_result,
                "export_result": export_result,
                "archive_result": archive_result,
            }
            (output_root / "pilot_package_build_manifest.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            raise SystemExit(int(archive_result["return_code"]))

    summary = {
        "artifact_name": "pilot_package_build_manifest.json",
        "overall_decision": "pass",
        "paper_outputs_root": str(paper_outputs_root),
        "paper_results_package_root": str(package_root),
        "drive_root": _optional_path(args.drive_root),
        "run_id": _optional_path(args.run_id),
        "build_result": build_result,
        "export_result": export_result,
        "archive_result": archive_result,
        "execution_digest": build_stable_digest(
            {
                "build_command": build_command,
                "export_command": export_command,
                "archive_result": archive_result,
            }
        ),
    }
    (output_root / "pilot_package_build_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
