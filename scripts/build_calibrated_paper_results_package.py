"""从真实 detection events 构建 fixed-FPR 校准后的论文结果包。

该脚本属于流程编排层, 不实现 CEG 方法本身。它把已经存在的三个独立步骤串联起来:
1. `calibrate_detection_events_fixed_fpr.py`: 根据 clean negative 事件校准 fixed FPR 阈值并回写 event payload。
2. `build_paper_outputs.py`: 使用已校准 events 运行 protocol runner 并重建论文表格、图表和报告。
3. `export_paper_results_package.py`: 导出可交付论文结果包。

这样可以避免人工忘记把 `detection_events_calibrated.json` 传给 `build_paper_outputs.py`, 从而保证
formal decision、TPP@FPR 表格和结果包使用同一组 fixed-FPR 阈值。
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


def _optional_path(value: str | None) -> str | None:
    """把空字符串规整为 None, 便于追加可选命令行参数。"""

    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    """当可选路径存在时追加命令行参数。"""

    if _optional_path(value) is not None:
        command.extend([flag, str(value)])


def _run_command(command: list[str]) -> dict[str, Any]:
    """执行子命令并返回可写入 manifest 的摘要。"""

    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _fail_manifest(output_root: Path, *, failed_step: str, results: dict[str, Any]) -> None:
    """写出失败 manifest 并终止流程。"""

    manifest = {
        "artifact_name": "calibrated_paper_results_package_build_manifest.json",
        "overall_decision": "fail",
        "failed_step": failed_step,
        **results,
    }
    (output_root / "calibrated_paper_results_package_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="从 detection_events.json 构建 fixed-FPR 校准后的论文结果包。")
    parser.add_argument("--detection-events", required=True, help="真实 detection_events.json 路径。")
    parser.add_argument("--out", required=True, help="输出根目录。")
    parser.add_argument("--target-fpr", type=float, default=0.01, help="目标 clean negative FPR。")
    parser.add_argument("--score-field", default="content_score_raw", help="payload.content 中用于校准的分数字段。")
    parser.add_argument("--calibration-split", default="calibration", help="优先用于阈值校准的 split。")
    parser.add_argument("--negative-role", action="append", default=None, help="用于校准的负样本角色, 可重复传入。")
    parser.add_argument("--profile", default="paper_main_probe", help="paper protocol profile。")
    parser.add_argument("--baseline-observations", default=None)
    parser.add_argument("--baseline-execution-manifest", default=None)
    parser.add_argument("--metric-rows", default=None)
    parser.add_argument("--metric-execution-manifest", default=None)
    parser.add_argument("--image-pairs", default=None)
    parser.add_argument("--attacked-image-manifest", default=None)
    parser.add_argument("--attack-shard-manifest", default=None)
    parser.add_argument("--experiment-matrix", default=None)
    parser.add_argument("--readiness-requirements", default=None)
    parser.add_argument("--require-paper-readiness", action="store_true")
    parser.add_argument("--allow-incomplete-package", action="store_true", help="允许 readiness 未通过时导出调试包。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    calibrated_root = output_root / "calibrated_detection"
    paper_outputs_root = output_root / "paper_outputs"
    package_root = output_root / "paper_results_package"

    calibration_command = [
        sys.executable,
        str(ROOT / "scripts" / "calibrate_detection_events_fixed_fpr.py"),
        "--events",
        str(args.detection_events),
        "--out",
        str(calibrated_root),
        "--target-fpr",
        str(args.target_fpr),
        "--score-field",
        str(args.score_field),
        "--calibration-split",
        str(args.calibration_split),
    ]
    for role in args.negative_role or ["clean_negative"]:
        calibration_command.extend(["--negative-role", str(role)])
    calibration_result = _run_command(calibration_command)
    if calibration_result["return_code"] != 0:
        _fail_manifest(output_root, failed_step="calibrate_detection_events_fixed_fpr", results={"calibration_result": calibration_result})
        raise SystemExit(int(calibration_result["return_code"]))

    calibrated_events = calibrated_root / "detection_events_calibrated.json"
    calibrated_thresholds = calibrated_root / "detection_thresholds_calibrated.json"
    calibration_report = calibrated_root / "detection_event_threshold_calibration_report.json"
    build_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_paper_outputs.py"),
        "--events",
        str(calibrated_events),
        "--thresholds",
        str(calibrated_thresholds),
        "--profile",
        str(args.profile),
        "--detection-execution-manifest",
        str(calibration_report),
        "--out",
        str(paper_outputs_root),
    ]
    _append_optional(build_command, "--baseline-observations", args.baseline_observations)
    _append_optional(build_command, "--baseline-execution-manifest", args.baseline_execution_manifest)
    _append_optional(build_command, "--metric-rows", args.metric_rows)
    _append_optional(build_command, "--metric-execution-manifest", args.metric_execution_manifest)
    _append_optional(build_command, "--image-pairs", args.image_pairs)
    _append_optional(build_command, "--attacked-image-manifest", args.attacked_image_manifest)
    _append_optional(build_command, "--attack-shard-manifest", args.attack_shard_manifest)
    _append_optional(build_command, "--experiment-matrix", args.experiment_matrix)
    _append_optional(build_command, "--readiness-requirements", args.readiness_requirements)
    if args.require_paper_readiness:
        build_command.append("--require-paper-readiness")
    build_result = _run_command(build_command)
    if build_result["return_code"] != 0:
        _fail_manifest(
            output_root,
            failed_step="build_paper_outputs",
            results={"calibration_result": calibration_result, "build_result": build_result},
        )
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
        _fail_manifest(
            output_root,
            failed_step="export_paper_results_package",
            results={
                "calibration_result": calibration_result,
                "build_result": build_result,
                "export_result": export_result,
            },
        )
        raise SystemExit(int(export_result["return_code"]))

    manifest = {
        "artifact_name": "calibrated_paper_results_package_build_manifest.json",
        "overall_decision": "pass",
        "input_detection_events": str(args.detection_events),
        "calibrated_detection_root": str(calibrated_root),
        "calibrated_events_path": str(calibrated_events),
        "calibrated_thresholds_path": str(calibrated_thresholds),
        "calibration_report_path": str(calibration_report),
        "paper_outputs_root": str(paper_outputs_root),
        "paper_results_package_root": str(package_root),
        "calibration_result": calibration_result,
        "build_result": build_result,
        "export_result": export_result,
        "execution_digest": build_stable_digest(
            {
                "calibration_command": calibration_command,
                "build_command": build_command,
                "export_command": export_command,
            }
        ),
    }
    (output_root / "calibrated_paper_results_package_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
