"""把已提供的 pilot 产物整理为统一输入目录并生成 manifest."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from main.core.digest import build_stable_digest
from experiments.pilot_input_manifest import validate_pilot_input_manifest

PILOT_INPUT_MATERIALIZATION_MANIFEST_NAME = "pilot_input_materialization_manifest.json"

CANONICAL_PILOT_INPUT_PATHS = {
    "events": "ceg_detection/detection_events.json",
    "thresholds": "ceg_detection/detection_thresholds.json",
    "baseline_observations": "external_baselines/baseline_observations.json",
    "baseline_execution_manifest": "external_baselines/baseline_execution_manifest.json",
    "metric_rows": "external_metrics/metric_rows.json",
    "metric_execution_manifest": "external_metrics/metric_execution_manifest.json",
    "detection_execution_manifest": "ceg_detection/ceg_detection_execution_manifest.json",
    "image_pairs": "inputs/image_pairs.json",
    "attacked_image_manifest": "image_attacks/image_manifests/attacked_image_manifest.json",
    "attack_shard_manifest": "image_attacks/image_manifests/attack_shard_manifest.json",
    "experiment_matrix": "plans/paper_experiment_matrix.json",
    "readiness_requirements": "configs/paper_output_requirements.json",
}


def _normalize_source_path(value: str | Path | None) -> Path | None:
    """把空路径规范为 None, 便于可选输入复用同一处理逻辑."""
    if value is None or str(value).strip() == "":
        return None
    return Path(value)


def _copy_input_file(source_path: Path, destination_path: Path) -> dict[str, Any]:
    """复制单个输入文件并记录可审计证据.

    此处属于通用工程写法: 物化目录保存文件副本, 而不是只保存源路径引用.
    这样后续构建 paper_results_package 时可以固定读取同一输入根目录, 减少外部路径变动造成的不可复现风险.
    """
    if not source_path.is_file():
        return {
            "source_path": str(source_path),
            "destination_path": str(destination_path),
            "status": "fail",
            "reason": "source_file_missing",
        }
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    return {
        "source_path": str(source_path),
        "destination_path": str(destination_path),
        "status": "pass",
        "size_bytes": destination_path.stat().st_size,
    }


def materialize_pilot_input_bundle(
    output_root: str | Path,
    *,
    events: str | Path | None = None,
    thresholds: str | Path | None = None,
    baseline_observations: str | Path | None = None,
    baseline_execution_manifest: str | Path | None = None,
    metric_rows: str | Path | None = None,
    metric_execution_manifest: str | Path | None = None,
    detection_execution_manifest: str | Path | None = None,
    image_pairs: str | Path | None = None,
    attacked_image_manifest: str | Path | None = None,
    attack_shard_manifest: str | Path | None = None,
    experiment_matrix: str | Path | None = None,
    readiness_requirements: str | Path | None = None,
    detection_output_root: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """将已提供产物复制到 canonical pilot 输入目录并写出 pilot_input_manifest.json.

    项目特定写法:
    - `events` 与 `thresholds` 是最小必需输入, 用于后续构建论文表格和 readiness 报告.
    - baseline、metric、image、attack 等输入按论文结果包目录语义放入固定子目录.
    - 函数只整理和校验输入, 不生成正式论文结果, 因而不会伪造模型或 baseline 输出.
    """
    output_path = Path(output_root)
    output_path.mkdir(parents=True, exist_ok=True)

    source_inputs = {
        "events": _normalize_source_path(events),
        "thresholds": _normalize_source_path(thresholds),
        "baseline_observations": _normalize_source_path(baseline_observations),
        "baseline_execution_manifest": _normalize_source_path(baseline_execution_manifest),
        "metric_rows": _normalize_source_path(metric_rows),
        "metric_execution_manifest": _normalize_source_path(metric_execution_manifest),
        "detection_execution_manifest": _normalize_source_path(detection_execution_manifest),
        "image_pairs": _normalize_source_path(image_pairs),
        "attacked_image_manifest": _normalize_source_path(attacked_image_manifest),
        "attack_shard_manifest": _normalize_source_path(attack_shard_manifest),
        "experiment_matrix": _normalize_source_path(experiment_matrix),
        "readiness_requirements": _normalize_source_path(readiness_requirements),
    }

    copied_inputs: dict[str, dict[str, Any]] = {}
    pilot_manifest: dict[str, Any] = {
        "artifact_name": "pilot_input_manifest.json",
        "materialized_by": "materialize_pilot_input_bundle",
    }
    if run_id:
        pilot_manifest["run_id"] = run_id

    for field, source_path in source_inputs.items():
        if source_path is None:
            continue
        relative_destination = CANONICAL_PILOT_INPUT_PATHS[field]
        destination_path = output_path / relative_destination
        copy_result = _copy_input_file(source_path, destination_path)
        copied_inputs[field] = copy_result
        if copy_result["status"] == "pass":
            pilot_manifest[field] = relative_destination

    if detection_output_root is not None and str(detection_output_root).strip() != "":
        # detection_output_root 只记录外部检测目录引用, 不复制整个目录树, 避免把大规模模型输出误放入输入束.
        pilot_manifest["detection_output_root"] = str(detection_output_root)

    pilot_manifest_path = output_path / "pilot_input_manifest.json"
    pilot_manifest_path.write_text(json.dumps(pilot_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_report = validate_pilot_input_manifest(pilot_manifest_path)
    validation_path = output_path / "pilot_input_manifest_validation.json"
    validation_path.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    missing_required = [field for field in ("events", "thresholds") if field not in pilot_manifest]
    copy_failures = {field: result for field, result in copied_inputs.items() if result["status"] != "pass"}
    materialization_manifest = {
        "artifact_name": PILOT_INPUT_MATERIALIZATION_MANIFEST_NAME,
        "overall_decision": "fail" if missing_required or copy_failures or validation_report["overall_decision"] != "pass" else "pass",
        "run_id": run_id,
        "pilot_input_manifest_path": str(pilot_manifest_path),
        "pilot_input_manifest_validation_path": str(validation_path),
        "source_inputs": {field: str(path) for field, path in source_inputs.items() if path is not None},
        "copied_inputs": copied_inputs,
        "missing_required_inputs": missing_required,
        "pilot_input_validation_decision": validation_report["overall_decision"],
        "materialization_digest": build_stable_digest(
            {
                "pilot_manifest": pilot_manifest,
                "copied_inputs": copied_inputs,
                "validation_decision": validation_report["overall_decision"],
            }
        ),
    }
    materialization_path = output_path / PILOT_INPUT_MATERIALIZATION_MANIFEST_NAME
    materialization_path.write_text(json.dumps(materialization_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return materialization_manifest
