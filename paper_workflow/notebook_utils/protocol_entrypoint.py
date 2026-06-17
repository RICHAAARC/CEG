"""Notebook 调用 CEG paper protocol 的轻量入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from experiments.pilot_input_value_pack import VALUE_PACK_NAME
from experiments.pilot_input_value_pack_sheet import FILL_SHEET_NAME
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

