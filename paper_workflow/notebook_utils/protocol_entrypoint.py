"""Notebook 调用 CEG paper protocol 的轻量入口。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from experiments.pilot_input_value_pack import VALUE_PACK_NAME
from experiments.pilot_input_value_pack_sheet import (
    FILL_SHEET_NAME,
    GUIDANCE_JSON_NAME,
    GUIDANCE_MARKDOWN_NAME,
    VALIDATION_MARKDOWN_NAME,
    VALIDATION_REPORT_NAME,
    export_pilot_input_value_pack_fill_sheet,
    export_pilot_input_value_pack_fill_sheet_guidance,
    validate_and_write_pilot_input_value_pack_fill_sheet,
)
from experiments.pilot_input_value_pack_status import (
    STATUS_MARKDOWN_NAME,
    STATUS_REPORT_NAME,
    write_pilot_input_value_pack_status,
)
from experiments.pilot_p0_input_freeze import (
    P0_INPUT_FREEZE_MARKDOWN_NAME,
    P0_INPUT_FREEZE_REPORT_NAME,
    write_pilot_p0_input_freeze_report,
)
from experiments.protocol_runner import run_paper_protocol
from paper_workflow.colab_utils.cold_start import build_colab_formal_run_checklist, run_colab_cold_start_pipeline, write_colab_formal_run_checklist


P0_INPUT_FREEZE_DRY_RUN_REPORT_NAME = "pilot_p0_input_freeze_dry_run_report.json"
P0_INPUT_FREEZE_DRY_RUN_MARKDOWN_NAME = "pilot_p0_input_freeze_dry_run_report.md"


def run_profile_from_notebook(
    event_rows: list[dict[str, Any]],
    *,
    profile: str,
    content_thresholds: dict[str, float],
) -> dict[str, Any]:
    """供 Notebook 调用的协议入口。

    Notebook 只负责传入事件 rows、profile 和阈值映射。正式协议执行、baseline 适配、结果聚合和产物构造均由 repository modules 完成。
    """
    return run_paper_protocol(event_rows, profile=profile, content_thresholds=content_thresholds)


def prepare_p0_input_materials_from_notebook(
    workspace_root: str | Path,
    *,
    value_pack_path: str | Path | None = None,
    fill_sheet_path: str | Path | None = None,
    guidance_markdown_path: str | Path | None = None,
    guidance_json_path: str | Path | None = None,
    status_json_path: str | Path | None = None,
    status_markdown_path: str | Path | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """供 Notebook 准备 P0 输入填写材料。

    该入口只调度 repository modules 导出 CSV 填写表、填写指南和 value pack
    状态报告。它不会生成真实 prompt、模型、水印参数或后续正式论文结果。
    """
    workspace = Path(workspace_root)
    value_pack = Path(value_pack_path) if value_pack_path is not None else workspace / VALUE_PACK_NAME
    fill_sheet = Path(fill_sheet_path) if fill_sheet_path is not None else workspace / FILL_SHEET_NAME
    guidance_markdown = (
        Path(guidance_markdown_path) if guidance_markdown_path is not None else workspace / GUIDANCE_MARKDOWN_NAME
    )
    guidance_json = Path(guidance_json_path) if guidance_json_path is not None else workspace / GUIDANCE_JSON_NAME
    status_json = Path(status_json_path) if status_json_path is not None else workspace / STATUS_REPORT_NAME
    status_markdown = Path(status_markdown_path) if status_markdown_path is not None else workspace / STATUS_MARKDOWN_NAME

    if fill_sheet.exists() and not overwrite_existing:
        with fill_sheet.open("r", encoding="utf-8-sig", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        fill_sheet_report = {
            "artifact_name": FILL_SHEET_NAME,
            "value_pack_path": str(value_pack),
            "output_csv_path": str(fill_sheet),
            "overall_decision": "pass",
            "row_count": row_count,
            "skipped_export": True,
            "reason": "existing_fill_sheet_preserved",
        }
    else:
        fill_sheet_report = export_pilot_input_value_pack_fill_sheet(
            value_pack_path=value_pack,
            output_csv_path=fill_sheet,
        )
    if guidance_markdown.exists() and guidance_json.exists() and not overwrite_existing:
        guidance_report = {
            "artifact_name": GUIDANCE_JSON_NAME,
            "value_pack_path": str(value_pack),
            "output_markdown_path": str(guidance_markdown),
            "output_json_path": str(guidance_json),
            "overall_decision": "pass",
            "guidance_only": True,
            "skipped_export": True,
            "reason": "existing_guidance_preserved",
            "summary": {"guidance_row_count": 0},
        }
    else:
        guidance_report = export_pilot_input_value_pack_fill_sheet_guidance(
            value_pack_path=value_pack,
            output_markdown_path=guidance_markdown,
            output_json_path=guidance_json,
        )
    status_report = write_pilot_input_value_pack_status(
        workspace_root=workspace,
        value_pack_path=value_pack,
        output_json_path=status_json,
        output_markdown_path=status_markdown,
    )
    blocking_count = int(status_report.get("summary", {}).get("blocking_item_count", 0))
    return {
        "artifact_name": "notebook_p0_input_materials_report.json",
        "workspace_root": str(workspace),
        "value_pack_path": str(value_pack),
        "overall_decision": "pass" if fill_sheet_report["overall_decision"] == "pass" and guidance_report["overall_decision"] == "pass" else "fail",
        "recommended_next_stage": "fill_value_json_and_run_p0_dry_run",
        "fill_sheet_report": fill_sheet_report,
        "guidance_report": guidance_report,
        "status_report": status_report,
        "output_paths": {
            "fill_sheet": str(fill_sheet),
            "guidance_markdown": str(guidance_markdown),
            "guidance_json": str(guidance_json),
            "status_json": str(status_json),
            "status_markdown": str(status_markdown),
        },
        "summary": {
            "fill_sheet_row_count": fill_sheet_report.get("row_count", 0),
            "guidance_row_count": guidance_report.get("summary", {}).get("guidance_row_count", 0),
            "value_pack_blocking_item_count": blocking_count,
            "overwrite_existing": overwrite_existing,
        },
    }


def validate_p0_fill_sheet_from_notebook(
    workspace_root: str | Path,
    *,
    value_pack_path: str | Path | None = None,
    fill_sheet_path: str | Path | None = None,
    output_json_path: str | Path | None = None,
    output_markdown_path: str | Path | None = None,
    require_pass: bool = False,
) -> dict[str, Any]:
    """供 Notebook 预检 P0 CSV 填写表。

    该入口只检查 `value_json` 是否可解析并满足 value pack 的基本类型要求。
    它不会回写 value pack, 因此适合在运行 P0 dry-run 前快速定位填写错误。
    """
    workspace = Path(workspace_root)
    value_pack = Path(value_pack_path) if value_pack_path is not None else workspace / VALUE_PACK_NAME
    fill_sheet = Path(fill_sheet_path) if fill_sheet_path is not None else workspace / FILL_SHEET_NAME
    output_json = Path(output_json_path) if output_json_path is not None else workspace / VALIDATION_REPORT_NAME
    output_markdown = (
        Path(output_markdown_path) if output_markdown_path is not None else workspace / VALIDATION_MARKDOWN_NAME
    )
    report = validate_and_write_pilot_input_value_pack_fill_sheet(
        value_pack_path=value_pack,
        input_csv_path=fill_sheet,
        report_path=output_json,
        markdown_report_path=output_markdown,
    )
    report["output_markdown_path"] = str(output_markdown)
    if require_pass and report["overall_decision"] != "pass":
        raise RuntimeError(f"P0 CSV 填写表预检未通过: {report['summary']['blocking_item_count']} 个阻断项")
    return report


def run_p0_input_freeze_from_notebook(
    workspace_root: str | Path,
    *,
    value_pack_path: str | Path | None = None,
    fill_sheet_path: str | Path | None = None,
    dry_run: bool = True,
    require_pass: bool = False,
    output_json_path: str | Path | None = None,
    output_markdown_path: str | Path | None = None,
) -> dict[str, Any]:
    """供 Notebook 调度 P0 输入冻结门禁。

    该入口只调用 repository module, 不在 Notebook helper 中实现 CSV 导入、
    value pack 应用或正式报告拼接逻辑。默认使用 dry-run, 目的是避免
    Notebook 单元格在未确认前改写真正的 pilot value pack 和输入模板。
    """
    workspace = Path(workspace_root)
    value_pack = Path(value_pack_path) if value_pack_path is not None else workspace / VALUE_PACK_NAME
    fill_sheet = Path(fill_sheet_path) if fill_sheet_path is not None else workspace / FILL_SHEET_NAME
    if output_json_path is None:
        output_json = workspace / (P0_INPUT_FREEZE_DRY_RUN_REPORT_NAME if dry_run else P0_INPUT_FREEZE_REPORT_NAME)
    else:
        output_json = Path(output_json_path)
    if output_markdown_path is None:
        output_markdown = workspace / (
            P0_INPUT_FREEZE_DRY_RUN_MARKDOWN_NAME if dry_run else P0_INPUT_FREEZE_MARKDOWN_NAME
        )
    else:
        output_markdown = Path(output_markdown_path)

    report = write_pilot_p0_input_freeze_report(
        workspace_root=workspace,
        value_pack_path=value_pack,
        fill_sheet_path=fill_sheet,
        dry_run=dry_run,
        output_json_path=output_json,
        output_markdown_path=output_markdown,
    )
    if require_pass and report["overall_decision"] != "pass":
        first_blocking = report.get("first_blocking_gate") or {}
        gate_id = first_blocking.get("gate_id", "unknown_gate")
        raise RuntimeError(f"P0 输入冻结门禁未通过: {gate_id}")
    return report


def run_colab_paper_outputs_from_notebook(
    repo_root: str | Path,
    workspace_root: str | Path,
    *,
    profile: str = "paper_main_probe",
    repetitions: int = 1,
    use_dry_run_inputs: bool = True,
    run_external_plans: bool = False,
    require_gpu_for_external_plans: bool = True,
    require_experiment_coverage: bool = False,
    events_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    sample_manifest_path: str | Path | None = None,
    compute_basic_image_metrics: bool = False,
    calibrate_thresholds: bool = False,
    threshold_target_fpr: float = 0.01,
    threshold_calibration_split: str = "calibration",
    baseline_observations_path: str | Path | None = None,
    metric_rows_path: str | Path | None = None,
    baseline_plan_path: str | Path | None = None,
    metric_plan_path: str | Path | None = None,
    baseline_root: str | Path | None = None,
    metric_root: str | Path | None = None,
    image_pairs_path: str | Path | None = None,
    reference_image_root: str | Path | None = None,
    generated_image_root: str | Path | None = None,
    image_prompt_rows_path: str | Path | None = None,
) -> dict[str, Any]:
    """供 Colab Notebook 一键运行论文结果链路的入口。

    该函数只编排 repository scripts, 不在 Notebook helper 中手写正式 records、tables、figures 或 reports。
    """
    return run_colab_cold_start_pipeline(
        repo_root,
        workspace_root,
        profile=profile,
        repetitions=repetitions,
        use_dry_run_inputs=use_dry_run_inputs,
        run_external_plans=run_external_plans,
        require_gpu_for_external_plans=require_gpu_for_external_plans,
        require_experiment_coverage=require_experiment_coverage,
        events_path=events_path,
        thresholds_path=thresholds_path,
        sample_manifest_path=sample_manifest_path,
        compute_basic_image_metrics=compute_basic_image_metrics,
        calibrate_thresholds=calibrate_thresholds,
        threshold_target_fpr=threshold_target_fpr,
        threshold_calibration_split=threshold_calibration_split,
        baseline_observations_path=baseline_observations_path,
        metric_rows_path=metric_rows_path,
        baseline_plan_path=baseline_plan_path,
        metric_plan_path=metric_plan_path,
        baseline_root=baseline_root,
        metric_root=metric_root,
        image_pairs_path=image_pairs_path,
        reference_image_root=reference_image_root,
        generated_image_root=generated_image_root,
        image_prompt_rows_path=image_prompt_rows_path,
    )


def build_colab_formal_run_checklist_from_notebook(
    repo_root: str | Path,
    workspace_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """供 Notebook 在正式运行前生成可审计的 Colab 运行清单。

    该入口只调度 repository helper, 不在 Notebook 中手写正式 records 或论文结果。
    """
    return build_colab_formal_run_checklist(repo_root, workspace_root, **kwargs)


def write_colab_formal_run_checklist_from_notebook(
    output_path: str | Path,
    repo_root: str | Path,
    workspace_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """供 Notebook 写出正式运行清单, 写文件动作仍由 repository helper 完成。"""
    return write_colab_formal_run_checklist(output_path, repo_root, workspace_root, **kwargs)

