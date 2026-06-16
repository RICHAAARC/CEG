"""从已提供的实验产物一键构建 pilot 论文结果包并可选归档到 Drive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.core.digest import build_stable_digest
from experiments.pilot_input_manifest import load_pilot_input_manifest, validate_pilot_input_manifest


def _optional_path(value: str | None) -> str | None:
    """把空字符串规范化为 None, 便于命令行可选参数复用."""
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选路径存在时追加命令行参数."""
    if _optional_path(value) is not None:
        command.extend([flag, str(value)])



def _resolve_manifest_path(manifest_path: Path, value: object) -> str | None:
    """将 manifest 中的相对路径解析为相对 manifest 所在目录的绝对路径.

    通用工程写法:
    - 命令行显式参数优先, manifest 只补齐没有显式传入的路径.
    - manifest 内部路径按 manifest 文件所在目录解析, 便于把一次 pilot 输入整体搬迁到其他目录复跑.
    """
    if value is None or str(value).strip() == "":
        return None
    path = Path(str(value))
    resolved = path if path.is_absolute() else manifest_path.parent / path
    return str(resolved)


def _merge_manifest_arg(args: argparse.Namespace, manifest: dict[str, object] | None, manifest_path: Path | None, field: str, attr: str | None = None) -> None:
    """用 pilot input manifest 补齐 argparse 中尚未显式提供的路径字段."""
    if manifest is None or manifest_path is None:
        return
    target_attr = attr or field
    if _optional_path(getattr(args, target_attr)) is not None:
        return
    resolved = _resolve_manifest_path(manifest_path, manifest.get(field))
    if resolved is not None:
        setattr(args, target_attr, resolved)

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
    parser.add_argument("--pilot-input-manifest", default=None, help="可选 pilot_input_manifest.json, 用于统一声明一键构建输入.")
    parser.add_argument("--allow-invalid-pilot-input", action="store_true", help="允许 pilot input preflight 失败后继续构建, 仅用于诊断.")
    parser.add_argument("--events", default=None, help="detection_events.json 或统一 event records 输入.")
    parser.add_argument("--thresholds", default=None, help="detection_thresholds.json 或 method threshold 映射.")
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
    parser.add_argument("--external-result-evidence-report", default=None, help="可选 external_result_evidence_report.json, 会复制到 paper outputs 并随结果包归档.")
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    output_root = Path(args.out)
    paper_outputs_root = output_root / "paper_outputs"
    package_root = output_root / "paper_results_package"
    output_root.mkdir(parents=True, exist_ok=True)

    pilot_input_report = None
    pilot_input_manifest = None
    pilot_input_manifest_path = Path(args.pilot_input_manifest) if _optional_path(args.pilot_input_manifest) else None
    if pilot_input_manifest_path is not None:
        pilot_input_manifest = load_pilot_input_manifest(pilot_input_manifest_path)
        pilot_input_report = validate_pilot_input_manifest(pilot_input_manifest_path)
        (output_root / "pilot_input_manifest_validation.json").write_text(
            json.dumps(pilot_input_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if pilot_input_report["overall_decision"] != "pass" and not args.allow_invalid_pilot_input:
            summary = {
                "artifact_name": "pilot_package_build_manifest.json",
                "overall_decision": "fail",
                "failed_step": "pilot_input_preflight",
                "pilot_input_manifest": str(pilot_input_manifest_path),
                "pilot_input_manifest_validation": pilot_input_report,
            }
            (output_root / "pilot_package_build_manifest.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            raise SystemExit(1)

    for manifest_field, attr in (
        ("events", "events"),
        ("thresholds", "thresholds"),
        ("baseline_observations", "baseline_observations"),
        ("baseline_execution_manifest", "baseline_execution_manifest"),
        ("metric_rows", "metric_rows"),
        ("metric_execution_manifest", "metric_execution_manifest"),
        ("detection_execution_manifest", "detection_execution_manifest"),
        ("image_pairs", "image_pairs"),
        ("attacked_image_manifest", "attacked_image_manifest"),
        ("attack_shard_manifest", "attack_shard_manifest"),
        ("experiment_matrix", "experiment_matrix"),
        ("readiness_requirements", "readiness_requirements"),
    ):
        _merge_manifest_arg(args, pilot_input_manifest, pilot_input_manifest_path, manifest_field, attr)

    if _optional_path(args.events) is None:
        parser.error("--events is required unless provided by --pilot-input-manifest")
    if _optional_path(args.thresholds) is None:
        parser.error("--thresholds is required unless provided by --pilot-input-manifest")

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
            "pilot_input_manifest": str(pilot_input_manifest_path) if pilot_input_manifest_path else None,
            "pilot_input_manifest_validation": pilot_input_report,
            "build_result": build_result,
        }
        (output_root / "pilot_package_build_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(int(build_result["return_code"]))

    external_result_evidence_report_path = None
    if _optional_path(args.external_result_evidence_report) is not None:
        source_report = Path(str(args.external_result_evidence_report))
        if not source_report.is_file():
            summary = {
                "artifact_name": "pilot_package_build_manifest.json",
                "overall_decision": "fail",
                "failed_step": "copy_external_result_evidence_report",
                "pilot_input_manifest": str(pilot_input_manifest_path) if pilot_input_manifest_path else None,
                "pilot_input_manifest_validation": pilot_input_report,
                "external_result_evidence_report": str(source_report),
                "error": "external_result_evidence_report_missing",
                "build_result": build_result,
            }
            (output_root / "pilot_package_build_manifest.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        target_report = paper_outputs_root / "external_result_evidence_report.json"
        target_report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_report, target_report)
        external_result_evidence_report_path = str(target_report)

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
            "pilot_input_manifest": str(pilot_input_manifest_path) if pilot_input_manifest_path else None,
            "pilot_input_manifest_validation": pilot_input_report,
            "build_result": build_result,
            "external_result_evidence_report_path": external_result_evidence_report_path,
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
                "pilot_input_manifest": str(pilot_input_manifest_path) if pilot_input_manifest_path else None,
                "pilot_input_manifest_validation": pilot_input_report,
                "build_result": build_result,
                "external_result_evidence_report_path": external_result_evidence_report_path,
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
        "pilot_input_manifest": str(pilot_input_manifest_path) if pilot_input_manifest_path else None,
        "pilot_input_manifest_validation": pilot_input_report,
        "build_result": build_result,
        "external_result_evidence_report_path": external_result_evidence_report_path,
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
