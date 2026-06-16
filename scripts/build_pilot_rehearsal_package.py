"""构建本地 pilot rehearsal 论文结果包。

该脚本用于在没有真实 SD / watermark / detector / external baseline 的情况下,
用仓库内 dry-run fixture 串联以下治理链路:

prompt / records fixture -> baseline / metric 导入 -> attack manifest -> pilot input materialization
-> external_result_evidence_report -> paper_result_evidence_report -> paper_results_package -> MyDrive 归档

该脚本的输出只能证明工程链路和结果包契约可运行, 不能作为正式论文实验结果。
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

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.core.digest import build_stable_digest


def _run_command(command: list[str]) -> dict[str, Any]:
    """执行子命令并返回可写入 rehearsal manifest 的摘要。"""
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _require_success(step_name: str, result: dict[str, Any], manifest_path: Path, summary: dict[str, Any]) -> None:
    """在 rehearsal 子步骤失败时写出 manifest 并中止。"""
    if int(result.get("return_code", -1)) == 0:
        return
    summary.update(
        {
            "overall_decision": "fail",
            "failed_step": step_name,
            "failed_result": result,
        }
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(int(result.get("return_code", 1)) or 1)


def build_parser() -> argparse.ArgumentParser:
    """构造 pilot rehearsal 命令行参数。"""
    parser = argparse.ArgumentParser(description="构建本地 dry-run pilot rehearsal 论文结果包, 用于验证结果包链路和归档门禁.")
    parser.add_argument("--out", required=True, help="rehearsal 工作目录, 不应指向 checked-in outputs 目录.")
    parser.add_argument("--drive-root", default=None, help="可选 MyDrive 风格归档根目录, 例如 D:\\content\\drive\\MyDrive\\CEG.")
    parser.add_argument("--run-id", default="pilot_rehearsal", help="rehearsal 运行标识, 同时用于归档文件名.")
    parser.add_argument("--profile", default="paper_main_probe", help="build_paper_outputs 使用的 profile.")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    output_root = Path(args.out)
    source_root = output_root / "source_inputs"
    imports_root = output_root / "imports"
    attack_root = output_root / "attack_outputs"
    detection_root = output_root / "ceg_detection"
    experiment_matrix_root = output_root / "experiment_matrix"
    materialized_root = output_root / "materialized_pilot_inputs"
    package_root = output_root / "pilot_package"
    manifest_path = output_root / "pilot_rehearsal_manifest.json"
    output_root.mkdir(parents=True, exist_ok=True)

    input_manifest = write_paper_dry_run_inputs(source_root)
    summary: dict[str, Any] = {
        "artifact_name": "pilot_rehearsal_manifest.json",
        "overall_decision": "running",
        "run_id": args.run_id,
        "profile": args.profile,
        "rehearsal_scope": "dry_run_contract_rehearsal_not_formal_paper_result",
        "output_root": str(output_root),
        "source_inputs_root": str(source_root),
        "materialized_input_root": str(materialized_root),
        "detection_root": str(detection_root),
        "experiment_matrix_root": str(experiment_matrix_root),
        "pilot_package_root": str(package_root),
        "drive_root": args.drive_root,
        "dry_run_input_manifest": input_manifest,
        "steps": {},
    }

    baseline_import_command = [
        sys.executable,
        str(ROOT / "scripts" / "import_baseline_observations.py"),
        "--observations",
        str(source_root / input_manifest["baseline_observations_path"]),
        "--out",
        str(imports_root / "baseline"),
    ]
    baseline_import = _run_command(baseline_import_command)
    summary["steps"]["import_baseline_observations"] = baseline_import
    _require_success("import_baseline_observations", baseline_import, manifest_path, summary)

    metric_import_command = [
        sys.executable,
        str(ROOT / "scripts" / "import_metric_rows.py"),
        "--metric-rows",
        str(source_root / input_manifest["metric_rows_path"]),
        "--out",
        str(imports_root / "metric"),
    ]
    metric_import = _run_command(metric_import_command)
    summary["steps"]["import_metric_rows"] = metric_import
    _require_success("import_metric_rows", metric_import, manifest_path, summary)

    attack_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_image_attack_workflow.py"),
        "--image-pairs",
        str(source_root / input_manifest["image_pairs_path"]),
        "--out",
        str(attack_root),
        "--attack-families",
        "brightness_contrast",
    ]
    attack_result = _run_command(attack_command)
    summary["steps"]["run_image_attack_workflow"] = attack_result
    _require_success("run_image_attack_workflow", attack_result, manifest_path, summary)

    detection_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_ceg_detection_producer.py"),
        "--image-pairs",
        str(source_root / input_manifest["image_pairs_path"]),
        "--attacked-image-manifest",
        str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
        "--out",
        str(detection_root),
    ]
    detection_result = _run_command(detection_command)
    summary["steps"]["run_ceg_detection_producer"] = detection_result
    _require_success("run_ceg_detection_producer", detection_result, manifest_path, summary)

    experiment_matrix_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_experiment_matrix.py"),
        "--config",
        str(ROOT / "configs" / "paper_experiment_matrix.json"),
        "--out",
        str(experiment_matrix_root),
    ]
    experiment_matrix_result = _run_command(experiment_matrix_command)
    summary["steps"]["build_experiment_matrix"] = experiment_matrix_result
    _require_success("build_experiment_matrix", experiment_matrix_result, manifest_path, summary)

    raw_builder_command = [
        sys.executable,
        str(ROOT / "scripts" / "build_pilot_package_from_raw_inputs.py"),
        "--materialized-input-root",
        str(materialized_root),
        "--out",
        str(package_root),
        "--run-id",
        str(args.run_id),
        "--profile",
        str(args.profile),
        "--events",
        str(detection_root / "detection_events.json"),
        "--thresholds",
        str(detection_root / "detection_thresholds.json"),
        "--baseline-observations",
        str(imports_root / "baseline" / "baseline_observations.json"),
        "--baseline-execution-manifest",
        str(imports_root / "baseline" / "baseline_execution_manifest.json"),
        "--metric-rows",
        str(imports_root / "metric" / "metric_rows.json"),
        "--metric-execution-manifest",
        str(imports_root / "metric" / "metric_execution_manifest.json"),
        "--detection-execution-manifest",
        str(detection_root / "ceg_detection_producer_manifest.json"),
        "--experiment-matrix",
        str(experiment_matrix_root / "experiment_matrix.json"),
        "--image-pairs",
        str(source_root / input_manifest["image_pairs_path"]),
        "--attacked-image-manifest",
        str(attack_root / "image_manifests" / "attacked_image_manifest.json"),
        "--attack-shard-manifest",
        str(attack_root / "image_manifests" / "attack_shard_manifest.json"),
        "--readiness-requirements",
        str(ROOT / "configs" / "paper_output_requirements.json"),
        "--require-paper-readiness",
        "--check-external-result-evidence",
        "--write-paper-result-evidence-report",
        "--allow-dry-run-paper-result-evidence",
        "--allow-missing-experiment-coverage",
    ]
    if args.drive_root:
        raw_builder_command.extend(["--drive-root", str(args.drive_root)])
    raw_builder_result = _run_command(raw_builder_command)
    summary["steps"]["build_pilot_package_from_raw_inputs"] = raw_builder_result
    _require_success("build_pilot_package_from_raw_inputs", raw_builder_result, manifest_path, summary)

    package_manifest_path = package_root / "paper_results_package" / "paper_results_package_manifest.json"
    raw_manifest_path = package_root / "pilot_raw_input_package_build_manifest.json"
    summary.update(
        {
            "overall_decision": "pass",
            "paper_results_package_manifest": str(package_manifest_path),
            "pilot_raw_input_package_build_manifest": str(raw_manifest_path),
            "execution_digest": build_stable_digest(
                {
                    "run_id": args.run_id,
                    "profile": args.profile,
                    "steps": summary["steps"],
                    "package_manifest_path": str(package_manifest_path),
                }
            ),
        }
    )
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
